from fastapi import APIRouter, Depends, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser
from app.models.session import Session as MasteringSession
from app.models.cert import RainCert
from app.schemas.session import SessionResponse
import json
import asyncio

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(
        select(MasteringSession).where(
            MasteringSession.id == session_id,
            MasteringSession.user_id == current_user.user_id,  # RLS: user_id enforced
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E200", "message": "Session not found"})
    return SessionResponse.model_validate(session)


@router.websocket("/{session_id}/status")
async def session_status_ws(
    websocket: WebSocket,
    session_id: UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Real-time session status via WebSocket. Poll DB every second until terminal state."""
    from app.core.security import decode_token
    from app.models.session import Session as MasteringSession
    from sqlalchemy import select

    try:
        payload = decode_token(token)
        user_id = UUID(payload["sub"])
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    terminal = {"complete", "failed"}

    try:
        while True:
            result = await db.execute(
                select(MasteringSession).where(
                    MasteringSession.id == session_id,
                    MasteringSession.user_id == user_id,
                )
            )
            session = result.scalar_one_or_none()
            if not session:
                await websocket.send_json({"error": "RAIN-E100", "message": "Session not found"})
                break

            await websocket.send_json({
                "session_id": str(session_id),
                "status": session.status,
                "output_lufs": float(session.output_lufs) if session.output_lufs is not None else None,
                "output_true_peak": float(session.output_true_peak) if session.output_true_peak is not None else None,
                "rain_score": session.rain_score,
                "error_code": session.error_code,
                "error_detail": session.error_detail,
            })

            if session.status in terminal:
                break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


@router.get("/{session_id}/cert")
async def get_rain_cert(
    session_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns the RAIN-CERT JSON + Ed25519 signature for a completed session."""
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    result = await db.execute(
        select(MasteringSession).where(
            MasteringSession.id == session_id,
            MasteringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E200", "message": "Session not found"})

    cert_result = await db.execute(
        select(RainCert).where(RainCert.session_id == session_id)
    )
    cert = cert_result.scalar_one_or_none()
    if not cert:
        raise HTTPException(404, detail={"code": "RAIN-E200", "message": "Certificate not yet issued"})

    return {
        "cert_id": str(cert.id),
        "session_id": str(cert.session_id),
        "input_hash": cert.input_hash,
        "output_hash": cert.output_hash,
        "wasm_hash": cert.wasm_hash,
        "model_version": cert.model_version,
        "processing_params_hash": cert.processing_params_hash,
        "content_scan_passed": cert.content_scan_passed,
        "signature": cert.signature,
        "signature_algorithm": "Ed25519",
        "issued_at": cert.issued_at.isoformat(),
    }
