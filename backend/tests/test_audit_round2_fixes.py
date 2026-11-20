"""Regression tests for the post-round-2 audit fixes (Hermes leg).

Covers (audit-3way-round2-hermes/AUDIT-REPORT.md):
  P1-1 cek konsistensi jalan di background + polling status
  P1-2 state kolaborasi persisten di DB (versi + presence)
  P1-3 upload subtitle streaming berbatas + whitelist model_size
  P2-1 secret webhook test tanpa default hardcoded
  P2-2 deteksi nama hantu: semua nama per episode
  P2-3 JWT WS via subprotocol (fallback query param tetap jalan)
  P2-4 tidak ada lagi datetime.utcnow() di file yang disebut audit
  P2-5 mobile/assets/icon.png ada (1024x1024)
"""
import asyncio
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import (
    User, Project, Character, Episode,
    CollabPresence, CollabRoomState,
)
from app.services.billing import TEST_WEBHOOK_SECRET, TestBillingProvider
from app.services.collab import collab_manager
from app.services.consistency import rule_based_issues
from app.services.subtitles import transcribe_file


async def _poll_check(client, auth_headers, project_id, check_id, tries=60):
    """Poll GET consistency-check sampai tidak running; kembalikan body."""
    body = None
    for _ in range(tries):
        r = await client.get(
            f"/api/v1/projects/{project_id}/consistency-checks/{check_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        if body["status"] != "running":
            break
        await asyncio.sleep(0.5)
    return body


# ------------------------------------------------------------------ P1-1
class TestConsistencyAsync:
    async def test_post_returns_running_while_llm_blocked(
        self, client, auth_headers, test_project, db
    ):
        """POST kembali 201 langsung sementara LLM diblokir; GET tunjukkan
        status running, lalu completed setelah LLM dilepas."""
        db.add(Character(project_id=test_project.id, name="Nadia", personality="lembut"))
        db.add(Character(project_id=test_project.id, name="Nadya", personality="tegas"))
        db.add(Episode(project_id=test_project.id, episode_number=1, title="EP1", outline="Nadia masuk kantor."))
        await db.commit()

        gate = asyncio.Event()

        async def _blocked_llm(*args, **kwargs):
            await asyncio.wait_for(gate.wait(), timeout=15)
            return []

        with patch("app.api.consistency.run_llm_check", _blocked_llm):
            post_task = asyncio.create_task(client.post(
                f"/api/v1/projects/{test_project.id}/consistency-check",
                headers=auth_headers,
            ))
            await asyncio.sleep(0.5)
            r = await client.get(
                f"/api/v1/projects/{test_project.id}/consistency-checks",
                headers=auth_headers,
            )
            assert r.status_code == 200
            checks = r.json()
            assert len(checks) == 1
            # LLM masih diblokir -> check harus berstatus running.
            assert checks[0]["status"] == "running"
            check_id = checks[0]["id"]
            gate.set()
            r = await post_task
            assert r.status_code == 201, r.text
            assert r.json()["id"] == check_id
            body = await _poll_check(client, auth_headers, test_project.id, check_id)
            assert body["status"] == "completed"
            assert body["issue_count"] >= 1
            assert any(i["type"] == "name_variant" for i in body["issues"])

    async def test_background_failure_marks_failed_not_500(
        self, client, auth_headers, test_project, db
    ):
        """Bila rule-based raise, check jadi FAILED (bukan 500 di POST)."""
        db.add(Character(project_id=test_project.id, name="Nadia"))
        await db.commit()
        with patch(
            "app.api.consistency.rule_based_issues",
            side_effect=RuntimeError("boom"),
        ):
            r = await client.post(
                f"/api/v1/projects/{test_project.id}/consistency-check",
                headers=auth_headers,
            )
            assert r.status_code == 201, r.text
            body = await _poll_check(
                client, auth_headers, test_project.id, r.json()["id"]
            )
            assert body["status"] == "failed"
            assert "boom" in (body["error_message"] or "")


# ------------------------------------------------------------------ P1-2
class TestCollabPersistent:
    async def test_rest_edit_version_persisted_in_db(
        self, client, auth_headers, test_project, db
    ):
        """Versi edit tersimpan di DB dan naik tiap edit — bukan memori."""
        for i in range(2):
            r = await client.post(
                f"/api/v1/projects/{test_project.id}/collab/edit",
                json={"resource": "project", "resource_id": str(test_project.id),
                      "field": "title", "value": f"Judul {i}"},
                headers=auth_headers,
            )
            assert r.status_code == 200, r.text
            assert r.json()["version"] == i + 1
        state = await db.get(CollabRoomState, test_project.id)
        assert state is not None
        assert state.version == 2
        # Simulasi restart proses: buang semua room in-memory.
        collab_manager.rooms.clear()
        r = await client.post(
            f"/api/v1/projects/{test_project.id}/collab/edit",
            json={"resource": "project", "resource_id": str(test_project.id),
                  "field": "title", "value": "Judul 2"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 3  # lanjut dari DB, bukan dari 0
        await db.refresh(state)
        assert state.version == 3

    async def test_stale_presence_pruned(self, client, auth_headers, test_project, db, test_user):
        """Presence basi (>5 menit tanpa heartbeat) dibersihkan saat dibaca."""
        old = CollabPresence(
            project_id=test_project.id, user_id=test_user.id, name="Lama",
            field=None, color="#22D3EE",
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
        )
        db.add(old)
        await db.commit()
        r = await client.get(
            f"/api/v1/projects/{test_project.id}/collab/presence", headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json() == []
        assert await db.get(CollabPresence, (test_project.id, test_user.id)) is None

    async def test_ws_join_and_leave_persist_presence(self, tmp_path):
        """Join WS menulis baris presence ke DB; disconnect menghapusnya."""
        from contextlib import asynccontextmanager
        from fastapi.testclient import TestClient
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.core.security import create_access_token, get_password_hash
        from app.db.session import Base
        from app.main import app

        file_url = f"sqlite+aiosqlite:///{tmp_path}/collab_persist.db"
        eng = create_async_engine(file_url)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        async with maker() as s:
            user = User(email="cp@example.com", hashed_password=get_password_hash("x" * 12),
                        full_name="CP User", is_active=True, is_verified=True)
            s.add(user)
            await s.commit()
            await s.refresh(user)
            project = Project(owner_id=user.id, title="CP Project", status="DRAFT")
            s.add(project)
            await s.commit()
            await s.refresh(project)
            user_id, project_id = user.id, project.id
        token = create_access_token(data={"sub": str(user_id)})

        @asynccontextmanager
        async def _noop_lifespan(app):
            yield

        with patch("app.api.collab.AsyncSessionLocal", lambda: maker()):
            with patch.object(app.router, "lifespan_context", _noop_lifespan):
                with TestClient(app) as tc:
                    with tc.websocket_connect(
                        f"/api/v1/projects/{project_id}/collab/ws?token={token}"
                    ) as ws:
                        msg = ws.receive_json()
                        assert msg["type"] == "presence"
                        assert len(msg["users"]) == 1
                        # Presence sudah di DB selama koneksi hidup.
                        async with maker() as s:
                            row = await s.get(CollabPresence, (project_id, user_id))
                            assert row is not None
                            assert row.name == "CP User"
                            state = await s.get(CollabRoomState, project_id)
                            assert state is None or state.version == 0
                    # Setelah disconnect, baris presence hilang (handler
                    # finally jalan asinkron — poll sebentar).
                    for _ in range(20):
                        async with maker() as s:
                            row = await s.get(CollabPresence, (project_id, user_id))
                        if row is None:
                            break
                        await asyncio.sleep(0.25)
                    assert row is None
        await eng.dispose()


# ------------------------------------------------------------------ P1-3
class TestSubtitleUploadHardening:
    def _wav_bytes(self, n_frames=1600):
        import math
        import struct
        import wave
        import io

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            frames = b"".join(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / 16000)))
                for i in range(n_frames)
            )
            w.writeframes(frames)
        return buf.getvalue()

    async def test_model_size_not_whitelisted_400(
        self, client, auth_headers, test_project, tmp_path
    ):
        with patch("app.api.subtitles._subtitle_dir", lambda: tmp_path):
            r = await client.post(
                f"/api/v1/projects/{test_project.id}/subtitles",
                params={"model_size": "large-v3"},
                files={"file": ("a.wav", self._wav_bytes(), "audio/wav")},
                headers=auth_headers,
            )
        assert r.status_code == 400, r.text
        assert "model_size" in r.text
        # File tidak ditulis ke disk.
        assert list(tmp_path.iterdir()) == []

    async def test_oversize_upload_rejected_without_full_read(
        self, client, auth_headers, test_project, tmp_path
    ):
        """Batas 0 MB (monkeypatched): file kecil pun ditolak dan file
        parsial tidak tertinggal — bukti streaming berbatas jalan."""
        with (
            patch("app.api.subtitles._subtitle_dir", lambda: tmp_path),
            patch("app.api.subtitles.MAX_AUDIO_MB", 0),
        ):
            r = await client.post(
                f"/api/v1/projects/{test_project.id}/subtitles",
                files={"file": ("a.wav", self._wav_bytes(), "audio/wav")},
                headers=auth_headers,
            )
        assert r.status_code == 400, r.text
        assert "terlalu besar" in r.text
        assert list(tmp_path.iterdir()) == []

    async def test_streaming_upload_writes_file(
        self, client, auth_headers, test_project, tmp_path
    ):
        """Jalur streaming normal: file utuh sampai ke disk, job dibuat."""
        with (
            patch("app.api.subtitles._subtitle_dir", lambda: tmp_path),
            patch("app.api.subtitles._run_transcription", new_callable=AsyncMock),
        ):
            data = self._wav_bytes()
            r = await client.post(
                f"/api/v1/projects/{test_project.id}/subtitles",
                params={"model_size": "tiny"},
                files={"file": ("a.wav", data, "audio/wav")},
                headers=auth_headers,
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["model_size"] == "tiny"
        saved = list(tmp_path.iterdir())
        assert len(saved) == 1
        assert saved[0].read_bytes() == data

    def test_transcribe_file_rejects_bad_model_size(self):
        with pytest.raises(ValueError, match="model_size tidak diizinkan"):
            transcribe_file("/nonexistent/a.wav", model_size="large-v3")


# ------------------------------------------------------------------ P2-1
class TestWebhookSecret:
    def test_no_hardcoded_default_secret(self):
        assert TEST_WEBHOOK_SECRET != "whsec_test_only_change_me"
        assert len(TEST_WEBHOOK_SECRET) >= 32

    def test_sign_verify_roundtrip(self):
        provider = TestBillingProvider()
        payload = b'{"type": "checkout.session.completed"}'
        sig = provider.sign_test_payload(payload)
        assert provider.verify_webhook_signature(payload, sig) is True
        assert provider.verify_webhook_signature(payload, "0" * 64) is False
        assert provider.verify_webhook_signature(b"tampered", sig) is False


# ------------------------------------------------------------------ P2-2
class TestGhostNames:
    def test_all_ghost_names_per_episode_reported(self):
        issues = rule_based_issues(
            [{"name": "Nadia"}],
            [{"episode_number": 1, "title": "EP1",
              "outline": "Budi datang ke kantor. Budi marah pada Nadia. "
                         "Siti tertawa melihat Budi. Siti pergi bersama Budi."}],
        )
        found = {i["character"] for i in issues if i["type"] == "continuity"}
        assert found == {"Budi", "Siti"}
        # Tiap nama hanya sekali (dedup), bukan per kemunculan.
        assert len([i for i in issues if i["type"] == "continuity"]) == 2


# ------------------------------------------------------------------ P2-3
class TestWsTokenAuth:
    def test_extract_ws_token_prefers_subprotocol(self):
        from app.api.collab import extract_ws_token

        class FakeWS:
            def __init__(self, headers):
                self.headers = headers

        token, sub = extract_ws_token(
            FakeWS({"sec-websocket-protocol": "collab, abc.def.ghi"}),
            "query-token",
        )
        assert token == "abc.def.ghi"
        assert sub == "collab"

    def test_extract_ws_token_falls_back_to_query(self):
        from app.api.collab import extract_ws_token

        class FakeWS:
            headers = {}

        token, sub = extract_ws_token(FakeWS(), "query-token")
        assert token == "query-token"
        assert sub is None

    def test_extract_ws_token_none_when_absent(self):
        from app.api.collab import extract_ws_token

        class FakeWS:
            headers = {}

        token, sub = extract_ws_token(FakeWS(), None)
        assert token is None

    async def test_ws_subprotocol_auth_end_to_end(self, tmp_path):
        """WS connect dengan subprotocol ['collab', jwt] tanpa query param."""
        from contextlib import asynccontextmanager
        from fastapi.testclient import TestClient
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from app.core.security import create_access_token, get_password_hash
        from app.db.session import Base
        from app.main import app

        file_url = f"sqlite+aiosqlite:///{tmp_path}/collab_subproto.db"
        eng = create_async_engine(file_url)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        async with maker() as s:
            user = User(email="sp@example.com", hashed_password=get_password_hash("x" * 12),
                        full_name="SP User", is_active=True, is_verified=True)
            s.add(user)
            await s.commit()
            await s.refresh(user)
            project = Project(owner_id=user.id, title="SP Project", status="DRAFT")
            s.add(project)
            await s.commit()
            await s.refresh(project)
            user_id, project_id = user.id, project.id
        token = create_access_token(data={"sub": str(user_id)})

        @asynccontextmanager
        async def _noop_lifespan(app):
            yield

        with patch("app.api.collab.AsyncSessionLocal", lambda: maker()):
            with patch.object(app.router, "lifespan_context", _noop_lifespan):
                with TestClient(app) as tc:
                    with tc.websocket_connect(
                        f"/api/v1/projects/{project_id}/collab/ws",
                        subprotocols=["collab", token],
                    ) as ws:
                        msg = ws.receive_json()
                        assert msg["type"] == "presence"
                        assert len(msg["users"]) == 1
        await eng.dispose()


# ------------------------------------------------------------------ P2-4
class TestNoUtcnow:
    @pytest.mark.parametrize("rel", [
        "app/services/billing.py",
        "app/api/consistency.py",
        "app/api/subtitles.py",
    ])
    def test_no_utcnow_in_audit_cited_files(self, rel):
        root = Path(__file__).resolve().parent.parent
        text = (root / rel).read_text()
        # Yang dilarang: pemanggilan deprecated datetime.utcnow() — bukan
        # nama helper _utcnow_naive() yang justru penggantinya.
        assert "datetime.utcnow" not in text, f"{rel} masih memakai datetime.utcnow()"


# ------------------------------------------------------------------ P2-5
class TestMobileIcon:
    def test_mobile_icon_exists_and_is_1024_png(self):
        root = Path(__file__).resolve().parent.parent.parent
        icon = root / "mobile" / "assets" / "icon.png"
        assert icon.exists(), "mobile/assets/icon.png tidak ada"
        raw = icon.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", raw[16:24])
        assert (width, height) == (1024, 1024)
