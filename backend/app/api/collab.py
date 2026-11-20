"""Kolaborasi real-time: WebSocket presence + edit bersama, plus REST
fallback (presence + edit op) untuk klien tanpa WS.

Auth WS — JWT diutamakan lewat subprotocol WebSocket:
  new WebSocket(url, ["collab", "<jwt>"])
Subprotocol tidak masuk access log (tidak seperti query string). Fallback
`?token=<jwt>` tetap didukung untuk klien lama; risikonya: token di
query bisa tercatat di access log server (uvicorn mencatat full path
termasuk query). Bila memungkinkan, pakai subprotocol saja.

State persisten (audit ronde 2, P1-2): nomor versi edit + presence
disimpan di DB (CollabRoomState/CollabPresence) — tahan restart dan
konsisten antar worker. Broadcast WS live tetap per-worker (tanpa Redis).

Pesan masuk: {"type": "presence", "field": "..."} atau
{"type": "edit", "resource": ..., "resource_id": ..., "field": ..., "value": ...}
Pesan keluar: {"type": "presence", "users": [...]},
{"type": "update", "resource": ..., "resource_id": ..., "field": ...,
 "value": ..., "by": ..., "version": n}, {"type": "error", "detail": ...}
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db, AsyncSessionLocal
from app.core.security import get_current_active_user
from app.models import User, Project, SeriesBible, Episode, Character
from app.schemas import CollabEditOp, CollabPresenceResponse
from app.services.collab import (
    collab_manager, validate_edit_op, Presence,
    bump_room_version, get_room_version, list_presence,
    remove_presence, upsert_presence,
)

router = APIRouter(prefix="/projects", tags=["collab"])

_RESOURCE_MODEL = {
    "project": Project,
    "series_bible": SeriesBible,
    "episode": Episode,
    "character": Character,
}

# Heartbeat presence: segarkan updated_at tiap N detik tanpa pesan masuk,
# supaya presence tidak dianggap basi saat user diam membaca.
PRESENCE_HEARTBEAT_SECONDS = 30


def extract_ws_token(websocket: WebSocket, query_token: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Ambil JWT WS + subprotocol yang akan di-accept.

    Urutan: (1) subprotocol `collab` — `Sec-WebSocket-Protocol:
    collab, <jwt>`; (2) fallback query param `?token=<jwt>`.
    Kembalikan (token, subprotocol) — subprotocol None bila pakai query.
    """
    offered = websocket.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in offered.split(",") if p.strip()]
    if len(parts) >= 2 and parts[0] == "collab":
        return parts[1], "collab"
    if query_token:
        return query_token, None
    return None, None


async def _get_project(db: AsyncSession, user: User, project_id: UUID) -> Project:
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == user.id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _apply_edit(db: AsyncSession, user: User, project_id: UUID, op: dict) -> None:
    """Terapkan op edit tervalidasi ke DB (dengan tenant check)."""
    model = _RESOURCE_MODEL[op["resource"]]
    result = await db.execute(select(model).where(model.id == UUID(op["resource_id"])))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"{op['resource']} tidak ditemukan")
    # Tenant check: resource harus milik proyek user.
    if op["resource"] == "project":
        if row.owner_id != user.id or row.id != project_id:
            raise ValueError("Bukan proyek milikmu")
    elif op["resource"] == "series_bible":
        if row.project_id != project_id:
            raise ValueError("Bible bukan dari proyek ini")
        proj = await db.get(Project, project_id)
        if proj is None or proj.owner_id != user.id:
            raise ValueError("Bukan proyek milikmu")
    elif op["resource"] == "episode":
        if row.project_id != project_id:
            raise ValueError("Episode bukan dari proyek ini")
    elif op["resource"] == "character":
        if row.project_id != project_id:
            raise ValueError("Karakter bukan dari proyek ini")
    setattr(row, op["field"], op["value"])
    await db.commit()


@router.websocket("/{project_id}/collab/ws")
async def collab_ws(
    websocket: WebSocket, project_id: UUID, token: Optional[str] = Query(default=None)
):
    # Auth JWT: utamakan subprotocol, fallback query param (lihat docstring).
    jwt_token, subprotocol = extract_ws_token(websocket, token)
    try:
        if not jwt_token:
            raise ValueError("token tidak ada")
        payload = jwt.decode(jwt_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = UUID(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=1008)
        return
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Project).where(and_(Project.id == project_id, Project.owner_id == user_id))
        )
        project = result.scalar_one_or_none()
        if project is None:
            await websocket.close(code=1008)
            return
        user = await db.get(User, user_id)
        # Sinkronkan cermin versi in-memory dari DB (tahan restart worker).
        room_version = await get_room_version(db, project_id)
    await websocket.accept(subprotocol=subprotocol)
    conn_id = str(uuid.uuid4())
    room = collab_manager.room(str(project_id))
    room.version = room_version
    name = (user.full_name or user.email) if user else str(user_id)
    async with AsyncSessionLocal() as db:
        await upsert_presence(db, project_id, user_id, name)
        users = await list_presence(db, project_id)
    await room.join(conn_id, websocket, Presence(user_id=str(user_id), name=name))
    await room.broadcast({"type": "presence", "users": users})
    try:
        while True:
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=PRESENCE_HEARTBEAT_SECONDS
                )
            except asyncio.TimeoutError:
                # Heartbeat: segarkan presence di DB supaya tidak basi.
                async with AsyncSessionLocal() as db:
                    await upsert_presence(db, project_id, user_id, name)
                continue
            mtype = msg.get("type")
            if mtype == "presence":
                field_name = msg.get("field")
                await room.set_field(str(user_id), field_name)
                async with AsyncSessionLocal() as db:
                    await upsert_presence(db, project_id, user_id, name, field_name)
                    users = await list_presence(db, project_id)
                await room.broadcast({"type": "presence", "users": users})
            elif mtype == "edit":
                try:
                    op = validate_edit_op(msg)
                    async with AsyncSessionLocal() as db:
                        user_obj = await db.get(User, user_id)
                        await _apply_edit(db, user_obj, project_id, op)
                        version = await bump_room_version(db, project_id)
                    room.version = version
                    await room.broadcast({
                        "type": "update", "resource": op["resource"],
                        "resource_id": op["resource_id"], "field": op["field"],
                        "value": op["value"], "by": str(user_id), "version": version,
                    }, exclude_conn=conn_id)
                    await websocket.send_json({"type": "ack", "version": version})
                except (ValueError, Exception) as e:  # noqa: BLE001
                    await websocket.send_json({"type": "error", "detail": str(e)[:300]})
            else:
                await websocket.send_json({"type": "error", "detail": f"tipe pesan tidak dikenal: {mtype}"})
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup disconnect HARUS jalan meski task dibatalkan: saat WS
        # ditutup, scope anyio bisa membatalkan task — tanpa shield, await
        # di finally langsung CancelledError dan presence DB tidak terhapus.
        # (Di uvicorn produksi, disconnect normal berupa WebSocketDisconnect
        # dan finally jalan biasa; shield tidak mengubah perilaku itu.)
        with anyio.CancelScope(shield=True):
            await room.leave(conn_id, str(user_id))
            collab_manager.drop_empty(str(project_id))
            async with AsyncSessionLocal() as db:
                await remove_presence(db, project_id, user_id)
                users = await list_presence(db, project_id)
            await room.broadcast({"type": "presence", "users": users})


@router.get("/{project_id}/collab/presence", response_model=list[CollabPresenceResponse])
async def get_presence(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    return [CollabPresenceResponse(**p) for p in await list_presence(db, project_id)]


@router.post("/{project_id}/collab/edit", response_model=dict)
async def post_edit_op(
    project_id: UUID, op: CollabEditOp,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    try:
        valid = validate_edit_op(op.model_dump(mode="json"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await _apply_edit(db, current_user, project_id, valid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    version = await bump_room_version(db, project_id)
    room = collab_manager.room(str(project_id))
    room.version = version
    await room.broadcast({
        "type": "update", "resource": valid["resource"],
        "resource_id": valid["resource_id"], "field": valid["field"],
        "value": valid["value"], "by": str(current_user.id), "version": version,
    })
    return {"ok": True, "version": version}
