"""Anonymous per-session identity via an HttpOnly cookie (no login)."""

import uuid

from fastapi import Request, Response

_COOKIE_NAME = "session_id"


def _valid_uuid(value: str | None) -> str | None:
    """Return the canonical uuid, else None; the id becomes a filesystem path, so it must be one."""
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def get_session_id(request: Request, response: Response) -> str:
    """FastAPI dependency: return the caller's session id, minting and setting a cookie if needed."""
    session_id = _valid_uuid(request.cookies.get(_COOKIE_NAME))
    if session_id is None:
        session_id = str(uuid.uuid4())
        response.set_cookie(
            key=_COOKIE_NAME,
            value=session_id,
            httponly=True,
            samesite="lax",
        )
    return session_id
