"""Auth routes — login, logout, and seed admin users."""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import text

from app.services.auth import (
    create_access_token,
    create_user,
    decode_access_token,
    delete_token_cookie,
    get_current_user,
    get_user_by_username,
    set_token_cookie,
    verify_password,
)
from app.views.dashboard import _render

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """Render the login page."""
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    html = _render("auth/login.html", request=request, error=error)
    return HTMLResponse(html)


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Authenticate user and set JWT cookie."""
    user = await get_user_by_username(username)
    if not user or not verify_password(password, user.hashed_password):
        return await login_page(request, error="Invalid username or password")

    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "display_name": user.display_name,
    })

    response = RedirectResponse(url="/dashboard", status_code=303)
    set_token_cookie(response, token)
    # Track login activity
    try:
        from app.database import async_session
        import uuid as _uuid
        async with async_session() as s:
            sid_val = str(_uuid.uuid4())
            await s.execute(
                text("""INSERT INTO user_activity_events (company_id, user_id, session_id, event_type, route, occurred_at)
                   VALUES ((SELECT id FROM subscribers LIMIT 1), :uid, :sid, 'user_login', '/auth/login', NOW())"""),
                {"uid": username, "sid": sid_val}
            )
            await s.commit()
    except Exception:
        pass
    return response


@router.get("/logout")
async def logout():
    """Clear the auth cookie and redirect to login."""
    response = RedirectResponse(url="/auth/login", status_code=303)
    delete_token_cookie(response)
    return response


@router.post("/seed-users")
async def seed_users():
    """Seed initial owner and project_manager accounts if they don't exist."""
    created = []
    for username, password, display_name, role in [
        ("jason", "owner123", "Jason (Owner)", "owner"),
        ("jimmy", "jimmy123", "Jimmy (PM)", "project_manager"),
    ]:
        existing = await get_user_by_username(username)
        if existing:
            created.append(f"{username} (already exists)")
        else:
            await create_user(username, password, display_name, role)
            created.append(f"{username} ({role})")

    return HTMLResponse("<pre>✅ Users:\n" + "\n".join(created) + "\n\nTry logging in with:\n  jason / owner123  (owner)\n  jimmy / jimmy123  (project_manager)\n</pre>")
