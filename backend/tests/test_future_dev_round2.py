"""Future-dev round 2 (20 Nov 2026): billing test-mode, timeline,
cek konsistensi karakter, subtitle (SRT/VTT + engine), kolaborasi WS/REST.
"""
import asyncio
import json

import pytest
from sqlalchemy import select

from app.main import app
from app.models import (
    User, Project, Character, Episode, Prompt, PromptType,
    Subscription,
)
from app.services.billing import TestBillingProvider, list_plans
from app.services.consistency import rule_based_issues, parse_llm_issues, merge_issues
from app.services.subtitles import segments_to_srt, segments_to_vtt, engine_available
from app.services.collab import validate_edit_op


# ---------------------------------------------------------------- billing
async def test_billing_plans(client, auth_headers):
    r = await client.get("/api/v1/billing/plans", headers=auth_headers)
    assert r.status_code == 200
    plans = r.json()
    assert {p["id"] for p in plans} == {"free", "pro", "studio"}
    assert all(p["price_idr"] >= 0 for p in plans)


async def test_billing_subscription_default_free_inactive(client, auth_headers):
    r = await client.get("/api/v1/billing/subscription", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["plan"] == "free"
    assert r.json()["provider"] == "test"


async def test_billing_checkout_pro_is_test_mode(client, auth_headers, db):
    r = await client.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "test"
    assert "test" in body["checkout_url"]
    assert body["plan"]["id"] == "pro"
    # Tidak ada charge nyata: subscription masih inactive sampai webhook.
    sub = (await db.execute(select(Subscription))).scalar_one()
    assert sub.plan == "pro"
    assert sub.status.value == "inactive"


async def test_billing_checkout_unknown_plan_400(client, auth_headers):
    r = await client.post("/api/v1/billing/checkout", json={"plan": "enterprise"}, headers=auth_headers)
    assert r.status_code == 400


async def test_billing_checkout_free_activates_directly(client, auth_headers, db):
    r = await client.post("/api/v1/billing/checkout", json={"plan": "free"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["note"].startswith("Plan Free aktif")
    sub = (await db.execute(select(Subscription))).scalar_one()
    assert sub.status.value == "active"


async def test_billing_webhook_valid_signature_activates(client, auth_headers, test_user, db):
    provider = TestBillingProvider()
    await client.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=auth_headers)
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {"user_id": str(test_user.id)},
    }).encode()
    sig = provider.sign_test_payload(payload)
    r = await client.post(
        "/api/v1/billing/webhook", content=payload,
        headers={"X-Test-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True
    sub = (await db.execute(select(Subscription))).scalar_one()
    assert sub.status.value == "active"
    assert sub.current_period_end is not None


async def test_billing_webhook_bad_signature_401(client, auth_headers):
    payload = json.dumps({"type": "checkout.session.completed", "data": {}}).encode()
    r = await client.post(
        "/api/v1/billing/webhook", content=payload,
        headers={"X-Test-Signature": "0" * 64, "Content-Type": "application/json"},
    )
    assert r.status_code == 401


async def test_billing_cancel(client, auth_headers, db):
    await client.post("/api/v1/billing/checkout", json={"plan": "pro"}, headers=auth_headers)
    r = await client.post("/api/v1/billing/cancel", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "canceled"
    assert r.json()["plan"] == "free"


def test_list_plans_pure():
    assert [p["id"] for p in list_plans()] == ["free", "pro", "studio"]


# ---------------------------------------------------------------- timeline
async def test_timeline_crud(client, auth_headers, test_project, db):
    ep = Episode(project_id=test_project.id, episode_number=1, title="EP1", outline="x")
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    url = f"/api/v1/projects/{test_project.id}/episodes/{ep.id}/timeline"

    r = await client.get(url, headers=auth_headers)
    assert r.status_code == 404

    clips = [
        {"id": "c1", "track": 0, "start": 0, "duration": 8, "label": "Shot 1"},
        {"id": "c2", "track": 0, "start": 8, "duration": 8, "label": "Shot 2"},
    ]
    r = await client.post(url, json={"name": "Main", "clips": clips, "fps": 30}, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["duration_seconds"] == 16.0

    r = await client.post(url, json={"name": "Dup", "clips": []}, headers=auth_headers)
    assert r.status_code == 409

    r = await client.patch(url, json={"clips": [clips[0]]}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["duration_seconds"] == 8.0

    r = await client.get(url, headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["clips"]) == 1

    r = await client.delete(url, headers=auth_headers)
    assert r.status_code == 204
    r = await client.get(url, headers=auth_headers)
    assert r.status_code == 404


async def test_timeline_from_prompts(client, auth_headers, test_project, db):
    ep = Episode(project_id=test_project.id, episode_number=2, title="EP2", outline="x")
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    for i, title in enumerate(["Shot A", "Shot B"]):
        db.add(Prompt(
            project_id=test_project.id, episode_id=ep.id,
            prompt_type=PromptType.VIDEO_GENERATION,
            title=title, prompt_text=f"video prompt {title}",
        ))
    await db.commit()
    url = f"/api/v1/projects/{test_project.id}/episodes/{ep.id}/timeline/from-prompts"
    r = await client.post(url, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["clips"]) == 2
    assert body["duration_seconds"] == 16.0
    assert body["clips"][1]["start"] == 8.0


async def test_timeline_other_user_404(client, auth_headers2, test_project, db):
    ep = Episode(project_id=test_project.id, episode_number=3, title="EP3", outline="x")
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    r = await client.get(
        f"/api/v1/projects/{test_project.id}/episodes/{ep.id}/timeline",
        headers=auth_headers2,
    )
    assert r.status_code == 404


# ------------------------------------------------------------- consistency
def test_rule_based_name_variant():
    issues = rule_based_issues(
        [{"name": "Nadia"}, {"name": "Nadya"}, {"name": "Raka"}],
        [],
    )
    assert len(issues) == 1
    assert issues[0]["type"] == "name_variant"
    assert issues[0]["severity"] == "medium"


def test_rule_based_unknown_name_in_outline():
    issues = rule_based_issues(
        [{"name": "Nadia"}],
        [{"episode_number": 1, "title": "EP1",
          "outline": "Budi datang ke kantor. Budi marah pada Nadia. Budi pergi."}],
    )
    assert any(i["character"] == "Budi" for i in issues)


def test_parse_llm_issues_tolerant():
    raw = 'Berikut hasilnya:\n```json\n[{"character": "Nadia", "episode_number": 2, "type": "appearance", "severity": "high", "description": "Rambut berubah", "suggestion": "Samakan"}]\n```'
    issues = parse_llm_issues(raw)
    assert len(issues) == 1
    assert issues[0]["type"] == "appearance"
    assert parse_llm_issues("bukan json") == []
    assert parse_llm_issues("") == []


def test_merge_issues_dedups():
    a = {"character": "Nadia", "episode_number": 1, "type": "appearance", "description": "x", "severity": "low", "suggestion": ""}
    assert len(merge_issues([a], [dict(a)])) == 1


async def test_consistency_check_endpoint(client, auth_headers, test_project, db):
    db.add(Character(project_id=test_project.id, name="Nadia", personality="lembut", physical_appearance="rambut panjang"))
    db.add(Character(project_id=test_project.id, name="Nadya", personality="tegas", physical_appearance="rambut pendek"))
    db.add(Episode(project_id=test_project.id, episode_number=1, title="EP1", outline="Nadia masuk kantor."))
    await db.commit()
    r = await client.post(
        f"/api/v1/projects/{test_project.id}/consistency-check", headers=auth_headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # POST kembali langsung (background, audit ronde 2 P1-1) — poll sampai selesai.
    assert body["status"] in ("running", "completed")
    check_id = body["id"]
    for _ in range(60):
        r = await client.get(
            f"/api/v1/projects/{test_project.id}/consistency-checks/{check_id}",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        if body["status"] != "running":
            break
        await asyncio.sleep(0.5)
    # LLM tanpa key -> gagal diam-diam; hasil rule-based tetap ada.
    assert body["status"] == "completed"
    assert body["issue_count"] >= 1
    assert any(i["type"] == "name_variant" for i in body["issues"])
    r = await client.get(
        f"/api/v1/projects/{test_project.id}/consistency-checks", headers=auth_headers
    )
    assert r.status_code == 200 and len(r.json()) == 1


async def test_consistency_check_no_characters_400(client, auth_headers, test_project):
    r = await client.post(
        f"/api/v1/projects/{test_project.id}/consistency-check", headers=auth_headers
    )
    assert r.status_code == 400


# --------------------------------------------------------------- subtitles
def test_segments_to_srt_and_vtt():
    segs = [
        {"start": 0.0, "end": 2.5, "text": "Halo, saya Nadia."},
        {"start": 3.0, "end": 5.0, "text": "Selamat datang."},
    ]
    srt = segments_to_srt(segs)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,500\nHalo, saya Nadia.")
    assert "2\n00:00:03,000 --> 00:00:05,000\nSelamat datang." in srt
    vtt = segments_to_vtt(segs)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.500" in vtt


def test_engine_available():
    # faster-whisper terpasang di venv kaki Hermes (pip install 20 Nov 2026).
    assert engine_available() is True


async def test_subtitle_from_segments_and_download(client, auth_headers, test_project):
    segs = [
        {"start": 0.0, "end": 2.0, "text": "Halo."},
        {"start": 2.5, "end": 4.0, "text": "Apa kabar?"},
    ]
    r = await client.post(
        f"/api/v1/projects/{test_project.id}/subtitles/from-segments",
        json={"language": "id", "segments": segs}, headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["engine"] == "manual-segments"
    assert len(body["segments"]) == 2
    job_id = body["id"]
    r = await client.get(
        f"/api/v1/projects/{test_project.id}/subtitles/{job_id}/download?fmt=srt",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert "Halo." in r.text
    r = await client.get(
        f"/api/v1/projects/{test_project.id}/subtitles/{job_id}/download?fmt=vtt",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.text.startswith("WEBVTT")


async def test_subtitle_engine_status(client, auth_headers):
    r = await client.get("/api/v1/projects/subtitles/engine", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["available"] is True


# ------------------------------------------------------------------ collab
def test_validate_edit_op_ok_and_rejects():
    op = validate_edit_op({
        "resource": "episode", "resource_id": "00000000-0000-0000-0000-000000000001",
        "field": "title", "value": "Baru",
    })
    assert op["field"] == "title"
    with pytest.raises(ValueError):
        validate_edit_op({"resource": "episode", "resource_id": "x", "field": "status", "value": "y"})
    with pytest.raises(ValueError):
        validate_edit_op({"resource": "user", "resource_id": "x", "field": "email", "value": "y"})


async def test_collab_rest_edit_updates_project(client, auth_headers, test_project, db):
    r = await client.post(
        f"/api/v1/projects/{test_project.id}/collab/edit",
        json={"resource": "project", "resource_id": str(test_project.id),
              "field": "title", "value": "Judul Kolaborasi"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["version"] >= 1
    proj = await db.get(Project, test_project.id)
    assert proj.title == "Judul Kolaborasi"


async def test_collab_rest_edit_forbidden_field(client, auth_headers, test_project):
    r = await client.post(
        f"/api/v1/projects/{test_project.id}/collab/edit",
        json={"resource": "project", "resource_id": str(test_project.id),
              "field": "owner_id", "value": "x"},
        headers=auth_headers,
    )
    assert r.status_code in (400, 422)


async def test_collab_presence_empty(client, auth_headers, test_project):
    r = await client.get(
        f"/api/v1/projects/{test_project.id}/collab/presence", headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_collab_websocket_presence_and_edit(tmp_path):
    """WS end-to-end: join -> presence -> edit episode -> update disiarkan
    ke koneksi kedua. Pakai file SQLite sementara (in-memory :memory:
    tidak terbagi antar event loop TestClient vs pytest-asyncio)."""
    from contextlib import asynccontextmanager
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.security import create_access_token, get_password_hash
    from app.db.session import Base

    file_url = f"sqlite+aiosqlite:///{tmp_path}/ws_test.db"
    eng = create_async_engine(file_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        user = User(email="ws@example.com", hashed_password=get_password_hash("x" * 12),
                    full_name="WS User", is_active=True, is_verified=True)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        project = Project(owner_id=user.id, title="WS Project", status="DRAFT")
        s.add(project)
        await s.commit()
        await s.refresh(project)
        ep = Episode(project_id=project.id, episode_number=1, title="Lama", outline="o")
        s.add(ep)
        await s.commit()
        await s.refresh(ep)
        user_id, project_id, ep_id = user.id, project.id, ep.id
    token = create_access_token(data={"sub": str(user_id)})

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    # WS handler tidak pakai get_db (pakai AsyncSessionLocal langsung,
    # di-patch ke engine file tes); lifespan init_db di-noop supaya
    # TestClient tidak mencoba connect Postgres DATABASE_URL default.
    with patch("app.api.collab.AsyncSessionLocal", lambda: maker()):
        with patch.object(app.router, "lifespan_context", _noop_lifespan):
            with TestClient(app) as tc:
                with tc.websocket_connect(
                    f"/api/v1/projects/{project_id}/collab/ws?token={token}"
                ) as ws1:
                    msg = ws1.receive_json()
                    assert msg["type"] == "presence"
                    assert len(msg["users"]) == 1
                    with tc.websocket_connect(
                        f"/api/v1/projects/{project_id}/collab/ws?token={token}"
                    ) as ws2:
                        msg2 = ws2.receive_json()
                        assert msg2["type"] == "presence"
                        # ws1 juga menerima broadcast presence dari join ws2 — drain.
                        drained = ws1.receive_json()
                        assert drained["type"] == "presence"
                        assert len(drained["users"]) == 1  # user sama, 1 presence
                        ws1.send_json({
                            "type": "edit", "resource": "episode",
                            "resource_id": str(ep_id), "field": "title",
                            "value": "Judul Baru WS",
                        })
                        ack = ws1.receive_json()
                        assert ack["type"] == "ack"
                        update = ws2.receive_json()
                        assert update["type"] == "update"
                        assert update["value"] == "Judul Baru WS"
    async with maker() as s:
        ep2 = await s.get(Episode, ep_id)
        assert ep2.title == "Judul Baru WS"
    await eng.dispose()


def test_load_audio_array_decodes_wav(tmp_path):
    """Decode wav 16k mono via ffmpeg -> array float32 (tanpa PyAV)."""
    import math
    import struct
    import wave

    from app.services.subtitles import _load_audio_array

    wav_path = tmp_path / "tone.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / 16000)))
            for i in range(16000)
        )
        w.writeframes(frames)
    audio = _load_audio_array(wav_path)
    assert len(audio) == 16000
    assert abs(float(audio.max())) <= 1.0


def test_transcribe_file_bypasses_pyav_with_fake_model(tmp_path, monkeypatch):
    """transcribe_file memanggil model dengan numpy array (bukan path),
    jadi jalur PyAV faster-whisper tidak dipakai."""
    import math
    import struct
    import wave

    from app.services import subtitles as sub_mod

    wav_path = tmp_path / "tone.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 16000)))
            for i in range(8000)
        ))

    seen: dict = {}

    class FakeSeg:
        def __init__(self, start, end, text):
            self.start, self.end, self.text = start, end, text

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, language=None):
            import numpy as np
            assert isinstance(audio, np.ndarray), "model harus menerima numpy array"
            seen["len"] = len(audio)
            return iter([FakeSeg(0.0, 1.0, "Halo.")]), {}

    import faster_whisper
    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeModel)
    segments = sub_mod.transcribe_file(wav_path, language="id")
    assert segments == [{"start": 0.0, "end": 1.0, "text": "Halo."}]
    assert seen["len"] == 8000


async def test_run_llm_check_with_fake_client():
    """Jalur LLM cek konsistensi: fake AIClient -> issue ter-parse."""
    from app.services.consistency import run_llm_check

    class FakeAIClient:
        async def chat_completion(self, messages, temperature=0.2, max_tokens=4000):
            assert any("Nadia" in m["content"] for m in messages)
            return {"content": '[{"character": "Nadia", "episode_number": 2, "type": "personality", "severity": "high", "description": "Nadia tiba-tiba kasar tanpa sebab.", "suggestion": "Beri pemicu perubahan sikap."}]'}

    issues = await run_llm_check(
        FakeAIClient(),
        [{"name": "Nadia", "personality": "lembut"}],
        [{"episode_number": 2, "title": "EP2", "outline": "Nadia membentak semua orang."}],
    )
    assert len(issues) == 1
    assert issues[0]["type"] == "personality"
    assert issues[0]["severity"] == "high"


async def test_run_llm_check_provider_failure_returns_empty():
    """LLM gagal -> [] (hasil rule-based tetap tersimpan, bukan exception)."""
    from app.services.consistency import run_llm_check

    class FailingClient:
        async def chat_completion(self, *a, **k):
            raise RuntimeError("provider down")

    issues = await run_llm_check(FailingClient(), [{"name": "Nadia"}], [])
    assert issues == []
