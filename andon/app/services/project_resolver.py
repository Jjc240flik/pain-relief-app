"""
Project Resolution Service — Map inbound messages to the correct project.

Resolution order:
1. Exact project_code match
2. Exact full street_address match
3. Unique address fragment match
4. Unique alias match
5. Sender assigned to exactly one active project
6. Multiple candidates → clarification required
"""

import logging
import re
from typing import Optional

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ProjectResolutionResult:
    """Result of attempting to resolve a project from an inbound message."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        method: str = "unresolved",
        confidence: float = 0.0,
        candidates: Optional[list] = None,
        clarification_required: bool = False,
    ):
        self.project_id = project_id
        self.method = method
        self.confidence = confidence
        self.candidates = candidates or []
        self.clarification_required = clarification_required


async def resolve_project(
    session: AsyncSession,
    text: str,
    sender_phone: str,
) -> ProjectResolutionResult:
    """Resolve the best project match for an inbound message.

    Returns a ProjectResolutionResult with the resolved project or candidates.
    """
    # 1. Exact project_code match
    if text:
        code_match = await _match_by_code(session, text)
        if code_match:
            return ProjectResolutionResult(
                project_id=code_match,
                method="project_code",
                confidence=1.0,
            )

    # 2. Exact full street_address match
    if text:
        addr_match = await _match_by_full_address(session, text)
        if addr_match:
            return ProjectResolutionResult(
                project_id=addr_match,
                method="full_address",
                confidence=1.0,
            )

    # 3. Unique address fragment
    if text:
        frag_match = await _match_by_address_fragment(session, text)
        if frag_match:
            return ProjectResolutionResult(
                project_id=frag_match,
                method="address_fragment",
                confidence=0.9,
            )

    # 4. Unique alias match
    if text:
        alias_match = await _match_by_alias(session, text)
        if alias_match:
            return ProjectResolutionResult(
                project_id=alias_match,
                method="alias",
                confidence=0.9,
            )

    # 5. Sender assigned to exactly one active project
    if sender_phone:
        sender_match = await _match_by_sender(session, sender_phone)
        if sender_match:
            return sender_match

    # 6. No match or multiple candidates
    candidates = await _find_candidates(session, text, sender_phone)
    if len(candidates) == 1:
        return ProjectResolutionResult(
            project_id=candidates[0]["id"],
            method=candidates[0].get("method", "single_candidate"),
            confidence=0.7,
        )
    elif len(candidates) > 1:
        return ProjectResolutionResult(
            method="clarification_required",
            confidence=0.0,
            candidates=candidates,
            clarification_required=True,
        )

    return ProjectResolutionResult(method="unresolved", confidence=0.0)


async def _match_by_code(session: AsyncSession, text: str) -> Optional[str]:
    """Check if message text contains a project code."""
    codes = await session.execute(
        sql_text("SELECT id, project_code FROM projects WHERE project_code IS NOT NULL")
    )
    for row in codes:
        if row.project_code and row.project_code.lower() in text.lower():
            return str(row.id)
    return None


async def _match_by_full_address(session: AsyncSession, text: str) -> Optional[str]:
    """Check if message text contains a full street address."""
    addresses = await session.execute(
        sql_text("SELECT id, street_address FROM projects WHERE street_address != ''")
    )
    for row in addresses:
        if row.street_address and row.street_address.lower() in text.lower():
            return str(row.id)
    return None


async def _match_by_address_fragment(session: AsyncSession, text: str) -> Optional[str]:
    """Check if message text contains a unique address fragment.

    Extracts potential address-like fragments (e.g., "1234 Lakeview")
    and checks if exactly one project matches.
    """
    # Common address patterns: number + street name
    fragments = re.findall(r'\b(\d+\s+\w+(?:\s+\w+)?)', text)
    if not fragments:
        return None

    matching = []
    for fragment in fragments:
        rows = await session.execute(
            sql_text(
                "SELECT id FROM projects WHERE "
                "street_address ILIKE :pattern AND street_address != ''"
            ),
            {"pattern": f"%{fragment}%"},
        )
        for row in rows:
            matching.append(str(row.id))

    if len(matching) == 1:
        return matching[0]
    return None


async def _match_by_alias(session: AsyncSession, text: str) -> Optional[str]:
    """Check if message text contains a unique alias."""
    rows = await session.execute(
        sql_text(
            "SELECT id, aliases FROM projects WHERE aliases IS NOT NULL AND aliases != '[]'::jsonb"
        )
    )
    matching = []
    for row in rows:
        aliases = row.aliases or []
        for alias in aliases:
            if isinstance(alias, str) and alias.lower() in text.lower():
                matching.append(str(row.id))
                break

    if len(matching) == 1:
        return matching[0]
    return None


async def _match_by_sender(session: AsyncSession, sender_phone: str) -> Optional[ProjectResolutionResult]:
    """Check if the sender is assigned to exactly one active project."""
    rows = await session.execute(
        sql_text(
            "SELECT DISTINCT pc.project_id FROM project_contacts pc "
            "JOIN contacts c ON c.id = pc.contact_id "
            "WHERE c.phone = :phone AND c.is_active = true AND pc.assignment_status = 'active'"
        ),
        {"phone": sender_phone},
    )
    projects = [str(row.project_id) for row in rows]

    if len(projects) == 1:
        return ProjectResolutionResult(
            project_id=projects[0],
            method="single_assigned_project",
            confidence=0.8,
        )
    return None


async def _find_candidates(session: AsyncSession, text: str, sender_phone: str) -> list:
    """Find all candidate projects that could match."""
    candidates = set()

    # Projects matching text fragments
    if text:
        rows = await session.execute(
            sql_text(
                "SELECT id, project_code, street_address FROM projects WHERE "
                "street_address != '' AND (street_address ILIKE :pattern "
                "OR project_code ILIKE :pattern)"
            ),
            {"pattern": f"%{text}%"},
        )
        for row in rows:
            candidates.add((str(row.id), "text_match"))

    # Projects where sender is assigned
    if sender_phone:
        rows = await session.execute(
            sql_text(
                "SELECT DISTINCT p.id FROM projects p "
                "JOIN project_contacts pc ON pc.project_id = p.id "
                "JOIN contacts c ON c.id = pc.contact_id "
                "WHERE c.phone = :phone AND c.is_active = true"
            ),
            {"phone": sender_phone},
        )
        for row in rows:
            candidates.add((str(row.id), "assigned_sender"))

    result = []
    for cid, method in candidates:
        result.append({"id": cid, "method": method})
    return result