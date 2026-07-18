"""
Admin endpoints for managing the ClassifierEngine.

Currently provides:
  - POST /admin/import-keywords — Import graded keywords from the Excel checklist
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Response

from app.services.keyword_loader import load_keywords_from_excel, format_report
from app.services.classifier import load_graded_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Expected location of the graded Excel file
EXCEL_PATH = Path(__file__).parent.parent.parent / "keywords_and_phrases_checklist.xlsx"


@router.post("/import-keywords")
async def import_keywords() -> Response:
    """
    Read the graded Excel checklist and update the ClassifierEngine rules.

    This triggers:
      1. Read keywords_and_phrases_checklist.xlsx
      2. Extract all Red/Yellow terms per trade
      3. Save to keywords_rules.json
      4. Reload rules into the ClassifierEngine (no restart needed)

    Returns a plain-text summary of what was imported.
    """
    if not EXCEL_PATH.exists():
        return Response(
            content=f"❌ Excel file not found: {EXCEL_PATH}\n"
                    "Please place the graded file at andon/keywords_and_phrases_checklist.xlsx",
            media_type="text/plain",
            status_code=404,
        )

    try:
        result = load_keywords_from_excel(str(EXCEL_PATH))
    except Exception as exc:
        logger.error("Failed to import keywords: %s", exc)
        return Response(
            content=f"❌ Import failed: {exc}",
            media_type="text/plain",
            status_code=500,
        )

    # Reload the rules into the classifier (no restart needed)
    load_graded_rules()

    report = format_report(result)
    logger.info("Keyword import complete:\n%s", report)
    return Response(content=report, media_type="text/plain")
