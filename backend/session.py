"""
session.py — anonymous per-session identity via an HttpOnly cookie.

There is no login. A random uuid4 in a cookie is the only thing scoping one
user's documents from another's, so the value is validated as a uuid before it
is ever used to build a filesystem path (a hand-crafted cookie must not be able
to escape its session folder).

Usage in a route:

    @app.get("/documents")
    def list_documents(session_id: str = Depends(get_session_id)):
        ...
"""

import uuid

from fastapi import Request, Response

_COOKIE_NAME = "session_id"


def _valid_uuid(value: str | None) -> str | None:
    """Return the canonical uuid string if `value` is a valid uuid, else None."""
    if not value:
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def get_session_id(request: Request, response: Response) -> str:
    """
    FastAPI dependency: return the caller's session id, minting one if the
    request has no valid session cookie. When a new id is minted it is set as an
    HttpOnly cookie on the response so the browser resends it automatically.
    """
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
