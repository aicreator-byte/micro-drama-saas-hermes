"""Kolaborasi real-time: presence + edit bersama via WebSocket.

Arsitektur (pasca audit ronde 2, P1-2):
- Koneksi WebSocket + broadcast tetap in-memory per proses (tidak bisa
  disimpan di DB) — satu room per proyek di CollabManager.
- State yang harus tahan restart dan konsisten antar worker disimpan di
  DB: nomor versi edit (CollabRoomState) dan daftar user online
  (CollabPresence). Proses baru / worker lain membaca versi + presence
  yang sama dari DB.
- Batasan yang tersisa: broadcast WS live hanya menjangkau koneksi di
  worker yang sama (tanpa Redis pub-sub). Edit dari worker lain tetap
  tersimpan di DB dan terlihat lewat REST GET presence / nomor versi,
  tapi tidak di-push real-time ke socket worker lain. Bila kolaborasi
  multi-worker penuh dibutuhkan, tambahkan Redis pub-sub di depan
  broadcast (REDIS_URL sudah ada di config).

Keamanan: WS memakai JWT — diutamakan via subprotocol WebSocket
`Sec-WebSocket-Protocol: collab, <token>` (lihat app/api/collab.py);
fallback `?token=` query param tetap didukung untuk klien lama, tapi
token di query bisa masuk access log server.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CollabPresence as CollabPresenceRow, CollabRoomState

# Presence yang tidak diperbarui lebih lama dari ini dianggap basi
# (proses mati mendadak tanpa disconnect bersih) dan dibersihkan saat dibaca.
PRESENCE_STALE_SECONDS = 300

# Field yang boleh diubah lewat kolaborasi (whitelist — bukan sembarang kolom).
EDITABLE_FIELDS: dict[str, set[str]] = {
    "project": {"title", "description", "genre"},
    "series_bible": {"premise", "main_plot", "tone", "visual_style", "world_settings", "ending_direction"},
    "episode": {"title", "outline", "production_notes"},
    "character": {"personality", "physical_appearance", "background", "costume"},
}


@dataclass
class Presence:
    user_id: str
    name: str
    field: Optional[str] = None  # mis. "series_bible.main_plot"
    color: str = "#22D3EE"


def _utcnow_naive() -> datetime:
    """UTC naive — sama seperti default kolom DateTime model lainnya."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------ DB: version
async def get_room_version(db: AsyncSession, project_id: UUID) -> int:
    """Nomor versi edit kolaboratif proyek dari DB (0 bila belum ada)."""
    row = await db.get(CollabRoomState, project_id)
    return row.version if row else 0


async def bump_room_version(db: AsyncSession, project_id: UUID) -> int:
    """Naikkan versi edit secara atomik (UPDATE ... SET version+1);
    kembalikan versi baru. Aman dipakai dua worker bersamaan."""
    stmt = (
        update(CollabRoomState)
        .where(CollabRoomState.project_id == project_id)
        .values(version=CollabRoomState.version + 1, updated_at=_utcnow_naive())
        .returning(CollabRoomState.version)
    )
    result = await db.execute(stmt)
    row = result.fetchone()
    if row is not None:
        await db.commit()
        return int(row[0])
    # Belum ada baris: buat dengan versi 1 (race kecil: bila worker lain
    # membuat duluan, IntegrityError -> rollback lalu baca versi hasil bump).
    from sqlalchemy.exc import IntegrityError

    db.add(CollabRoomState(project_id=project_id, version=1))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(stmt)
        row = result.fetchone()
        if row is not None:
            await db.commit()
            return int(row[0])
        return await get_room_version(db, project_id)
    return 1


# ------------------------------------------------------------ DB: presence
async def upsert_presence(
    db: AsyncSession, project_id: UUID, user_id: UUID,
    name: str, field_name: Optional[str] = None,
    color: str = "#22D3EE",
) -> None:
    """Tandai user online di room (join / set_field / heartbeat)."""
    row = await db.get(CollabPresenceRow, (project_id, user_id))
    now = _utcnow_naive()
    if row is None:
        db.add(CollabPresenceRow(
            project_id=project_id, user_id=user_id, name=name,
            field=field_name, color=color, updated_at=now,
        ))
    else:
        row.name = name
        row.field = field_name
        row.color = color
        row.updated_at = now
    await db.commit()


async def remove_presence(db: AsyncSession, project_id: UUID, user_id: UUID) -> None:
    """Hapus user dari presence (disconnect bersih)."""
    await db.execute(
        delete(CollabPresenceRow).where(
            CollabPresenceRow.project_id == project_id,
            CollabPresenceRow.user_id == user_id,
        )
    )
    await db.commit()


async def list_presence(db: AsyncSession, project_id: UUID) -> list[dict]:
    """Daftar presence proyek dari DB; baris basi dibersihkan dulu."""
    cutoff = _utcnow_naive() - timedelta(seconds=PRESENCE_STALE_SECONDS)
    await db.execute(
        delete(CollabPresenceRow).where(
            CollabPresenceRow.project_id == project_id,
            CollabPresenceRow.updated_at < cutoff,
        )
    )
    await db.commit()
    result = await db.execute(
        select(CollabPresenceRow)
        .where(CollabPresenceRow.project_id == project_id)
        .order_by(CollabPresenceRow.updated_at)
    )
    return [
        {"user_id": str(r.user_id), "name": r.name, "field": r.field, "color": r.color}
        for r in result.scalars().all()
    ]


# ------------------------------------------------------------ in-memory room
class CollabRoom:
    """Satu room = satu proyek. Hanya simpan koneksi WS hidup + cermin
    presence untuk broadcast; versi + presence otoritatif ada di DB."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.connections: dict[str, Any] = {}  # conn_id -> websocket
        self.presence: dict[str, Presence] = {}  # user_id -> Presence (cermin)
        self.version: int = 0  # cermin versi DB, disinkron saat join/bump
        self._lock = asyncio.Lock()

    async def join(self, conn_id: str, ws: Any, presence: Presence) -> None:
        async with self._lock:
            self.connections[conn_id] = ws
            self.presence[presence.user_id] = presence

    async def leave(self, conn_id: str, user_id: str) -> None:
        async with self._lock:
            self.connections.pop(conn_id, None)
            self.presence.pop(user_id, None)

    async def set_field(self, user_id: str, field_name: Optional[str]) -> None:
        async with self._lock:
            if user_id in self.presence:
                self.presence[user_id].field = field_name

    def presence_list(self) -> list[dict]:
        return [
            {"user_id": p.user_id, "name": p.name, "field": p.field, "color": p.color}
            for p in self.presence.values()
        ]

    async def broadcast(self, message: dict, exclude_conn: Optional[str] = None) -> None:
        payload = json.dumps(message)
        async with self._lock:
            targets = [(cid, ws) for cid, ws in self.connections.items() if cid != exclude_conn]
        for _cid, ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                pass  # koneksi mati — dibersihkan saat disconnect

    def bump_version(self) -> int:
        """Cermin in-memory saja — versi otoritatif di DB (bump_room_version)."""
        self.version += 1
        return self.version


class CollabManager:
    def __init__(self):
        self.rooms: dict[str, CollabRoom] = {}

    def room(self, project_id: str) -> CollabRoom:
        if project_id not in self.rooms:
            self.rooms[project_id] = CollabRoom(project_id)
        return self.rooms[project_id]

    def drop_empty(self, project_id: str) -> None:
        room = self.rooms.get(project_id)
        if room and not room.connections:
            self.rooms.pop(project_id, None)


# Singleton proses: hanya untuk koneksi WS + broadcast (bukan state).
collab_manager = CollabManager()


def validate_edit_op(op: dict) -> dict:
    """Validasi op edit; kembalikan op ternormalisasi atau raise ValueError."""
    resource = op.get("resource")
    field_name = op.get("field")
    if resource not in EDITABLE_FIELDS:
        raise ValueError(f"resource tidak dikenal: {resource}")
    if field_name not in EDITABLE_FIELDS[resource]:
        raise ValueError(f"field '{field_name}' tidak boleh diedit kolaboratif di {resource}")
    value = op.get("value")
    if not isinstance(value, str):
        raise ValueError("value harus string")
    if len(value) > 20000:
        raise ValueError("value terlalu panjang (maks 20000 karakter)")
    resource_id = op.get("resource_id")
    if not resource_id:
        raise ValueError("resource_id wajib")
    return {
        "resource": resource,
        "resource_id": str(resource_id),
        "field": field_name,
        "value": value,
    }
