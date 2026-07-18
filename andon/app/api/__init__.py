"""
API routes for the SMS Andon System.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health_check():
    """Health check endpoint — verifies the app is running."""
    return {"status": "ok", "service": "sms-andon"}
