"""
ClassifierEngine — Keyword-based message classification for MVP.

Maps inbound messages from subs to an Andon status (R/Y/G) using:
  1. Structured reply parsing (1/2/3/A/B)
  2. Keyword/pattern matching for "ISSUE" and emergency phrasing
  3. Selections keyword detection (paint, color, finish, etc.)

Per PRD mandate: simple keyword rules + confidence scoring.
Improve iteratively with real message data after launch.
"""

from dataclasses import dataclass
import re


TRADE_PHASES = [
    "foundation_concrete", "framing", "plumbing_rough", "hvac_rough",
    "electrical_rough", "drywall_plaster", "paint", "flooring",
    "cabinets", "finish_work",
]

# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

SELECTION_KEYWORDS = [
    "paint", "color", "finish", "selection", "what color",
    "hardware", "fixture", "countertop", "cabinet color",
    "floor color", "trim color", "door style", "what shade",
    "what colour",
]

RED_KEYWORDS = [
    "issue", "emergency", "broken", "leak", "flood", "fire",
    "structural", "collapsed", "collapse", "damage", "cannot start",
    "can't start", "not ready", "won't be there",
    "stop work", "shut down", "code violation",
    "inspection fail", "failed inspection",
    "water damage", "mold", "safety hazard",
    "blocking", "stop", "delay",
]

YELLOW_KEYWORDS = [
    "partial", "almost", "running late", "behind",
    "need material", "material short", "missing piece",
    "not finished", "half done",
    "cleanup", "no cleanup", "mess",
]


@dataclass
class ClassificationResult:
    """Result of classifying a single inbound message."""
    andon_status: str | None   # 'R', 'Y', or None (no change)
    confidence: float          # 0.0 – 1.0
    is_selections_query: bool  # If True, route to designer
    matched_keyword: str | None
    structured_reply: str | None  # e.g. '1', '2', '3', 'A', 'B'


class ClassifierEngine:
    """Stateless classifier — instantiate once per process."""

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify an inbound message and return the appropriate status.

        Processing order:
          1. Selection keyword check (forward to designer — no status change)
          2. Structured single-character reply (1/2/3/A/B) — highest confidence
          3. Red keywords
          4. Yellow keywords
          5. Default — no status change
        """
        if not text or not text.strip():
            return ClassificationResult(
                andon_status=None, confidence=0.0,
                is_selections_query=False, matched_keyword=None,
                structured_reply=None,
            )

        cleaned = text.strip().lower()

        # --- Check for selections query ---
        if self._check_selections(cleaned):
            return ClassificationResult(
                andon_status=None, confidence=0.9,
                is_selections_query=True,
                matched_keyword=self._first_match(cleaned, SELECTION_KEYWORDS),
                structured_reply=None,
            )

        # --- Structured single-character reply ---
        st = self._parse_structured(cleaned)
        if st and st[1] >= 0.95:
            status, confidence, matched = st
            return ClassificationResult(
                andon_status=status, confidence=confidence,
                is_selections_query=False, matched_keyword=matched,
                structured_reply=matched,
            )

        # --- Red keywords ---
        red_match = self._first_match(cleaned, RED_KEYWORDS)
        if red_match:
            return ClassificationResult(
                andon_status='R', confidence=0.8,
                is_selections_query=False, matched_keyword=red_match,
                structured_reply=None,
            )

        # --- Yellow keywords ---
        yellow_match = self._first_match(cleaned, YELLOW_KEYWORDS)
        if yellow_match:
            return ClassificationResult(
                andon_status='Y', confidence=0.6,
                is_selections_query=False, matched_keyword=yellow_match,
                structured_reply=None,
            )

        # --- No classifier triggered ---
        return ClassificationResult(
            andon_status=None, confidence=0.2,
            is_selections_query=False, matched_keyword=None,
            structured_reply=None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_selections(text: str) -> bool:
        return any(kw in text for kw in SELECTION_KEYWORDS)

    @staticmethod
    def _parse_structured(
        text: str,
    ) -> tuple[str, float, str] | None:
        """
        Parse known structured replies.

        Returns (status, confidence, matched_keyword)
        or None if not a structured reply.
        """
        text = text.strip().lower()

        # "ISSUE <description> at <address>" — always Red
        if text.startswith("issue"):
            return ('R', 0.95, 'issue_prefix')

        # Single character replies
        single_char_map = {
            '1': ('G', 0.98, '1'),
            '2': ('Y', 0.95, '2'),
            '3': ('R', 0.95, '3'),
            'a': ('G', 0.85, 'A'),
            'b': ('Y', 0.85, 'B'),
        }
        if text in single_char_map:
            return single_char_map[text]

        # "Yes", "No", "Issue"
        word_map = {
            'yes': ('G', 0.9, 'yes'),
            'no': ('Y', 0.8, 'no'),
            'done': ('G', 0.7, 'done'),
            'partial': ('Y', 0.7, 'partial'),
            'complete': ('G', 0.7, 'complete'),
            'clean': ('G', 0.6, 'clean'),
            'not clean': ('Y', 0.6, 'not_clean'),
            'not ready': ('R', 0.8, 'not_ready'),
        }
        if text in word_map:
            return word_map[text]

        return None

    @staticmethod
    def _first_match(text: str, keywords: list[str]) -> str | None:
        """Return the first keyword found in text, or None."""
        for kw in keywords:
            if kw in text:
                return kw
        return None
