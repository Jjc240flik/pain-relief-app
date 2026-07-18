"""
ClassifierEngine v3 — Trade-aware with multi-hit scoring and feedback tracking.

Improvements over v2:
  - Greatly expanded keyword lists with real construction language from Jimmy
  - Multi-hit scoring (more matched keywords = higher confidence, escalation)
  - Trade severity matrix (each trade has a base severity multiplier)
  - Medium-risk trade category (plumbing, electrical, HVAC)
  - Better ambiguous detection with topic clusters
  - Correction history tracked in result metadata
  - Feedback-ready: results carry event_id for quick correction linking

Pipeline order:
  1. Selection keyword check        (→ forward to designer)
  2. Structured single-char reply   (1/2/3/A/B — highest confidence)
  3. Trade-specific water check     (foundation = Red, others vary)
  4. Trade-specific structural check (framing/foundation = Red)
  5. Site cleanliness + escalation  (Yellow baseline, Red if blocking)
  6. General Red keywords           (multi-hit: 2+ matches → higher confidence)
  7. General Yellow keywords        (multi-hit: 3+ matches → upgrade to Red)
  8. Low confidence / ambiguous     (→ needs_review, no status change)

Operational language sourced from:
  - Jimmy's full interview transcript (cleanliness, water, concrete, framing)
  - Exterior & interior site walk checklists (debris, swept, shop vac, etc.)
  - PRD definitions of Red / Yellow
"""

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Graded keyword rules (loaded from keywords_rules.json)
# ---------------------------------------------------------------------------
_GRADED_RULES: dict | None = None


def load_graded_rules():
    """Load graded keyword rules from the persistent JSON file."""
    global _GRADED_RULES
    from app.services.keyword_loader import load_rules_from_json
    _GRADED_RULES = load_rules_from_json()


def get_graded_keywords(trade_name: str) -> tuple[list[str], list[str]]:
    """Get (red_keywords, yellow_keywords) for a trade from graded rules."""
    global _GRADED_RULES
    if _GRADED_RULES is None:
        load_graded_rules()
    if _GRADED_RULES and trade_name in _GRADED_RULES:
        rules = _GRADED_RULES[trade_name]
        return rules.get("red_keywords", []), rules.get("yellow_keywords", [])
    return [], []


# Mapping from internal trade IDs to Excel sheet names
TRADE_TO_SHEET_NAME = {
    "foundation_concrete": "Foundation Concrete",
    "framing": "Framing",
    "plumbing_rough": "Plumbing Rough",
    "hvac_rough": "HVAC Rough",
    "electrical_rough": "Electrical Rough",
    "drywall_plaster": "Drywall Plaster",
    "paint": "Paint",
    "flooring": "Flooring",
    "cabinets": "Cabinets",
    "finish_work": "Finish Work",
}


def _trade_to_sheet_name(internal_trade: str) -> str | None:
    """Convert internal trade ID (e.g. 'foundation_concrete') to Excel sheet name."""
    return TRADE_TO_SHEET_NAME.get(internal_trade)

# ---------------------------------------------------------------------------
# Trade risk levels — each trade has a severity multiplier
# ---------------------------------------------------------------------------

TRADE_SEVERITY = {
    "foundation_concrete": 1.3,  # Highest — structural, water-sensitive
    "framing": 1.25,             # High — structural, bones of the house
    "plumbing_rough": 1.1,       # Medium — water damage risk
    "hvac_rough": 1.0,           # Medium
    "electrical_rough": 1.0,     # Medium
    "drywall_plaster": 1.0,      # Standard
    "paint": 0.9,                # Lower — cosmetic
    "flooring": 0.9,             # Lower — cosmetic/finish
    "cabinets": 0.85,            # Lowest — finish work
    "finish_work": 0.85,         # Lowest — finish work
}

HIGH_RISK_TRADES = {"foundation_concrete", "framing"}
MEDIUM_RISK_TRADES = {"plumbing_rough", "hvac_rough", "electrical_rough"}
LOW_RISK_TRADES = {"drywall_plaster", "paint", "flooring", "cabinets", "finish_work"}

TRADE_PHASES = [
    "foundation_concrete", "framing", "plumbing_rough", "hvac_rough",
    "electrical_rough", "drywall_plaster", "paint", "flooring",
    "cabinets", "finish_work",
]

# ---------------------------------------------------------------------------
# Keyword lists — v3: expanded with real construction language
# ---------------------------------------------------------------------------

# --- 1. Selections / finishes — forward to designer ---
SELECTION_KEYWORDS = [
    "paint", "color", "finish", "selection", "what color",
    "hardware", "fixture", "countertop", "cabinet color",
    "floor color", "trim color", "door style", "what shade",
    "what colour", "cabinet style", "counter material",
    "backsplash", "appliance color", "light fixture",
    "faucet style", "door handle", "tile color",
    "what finish", "what stain", "what flooring",
    "interior paint", "wall color", "ceiling color",
    "what cabinet", "what trim",
]

# --- 2. Site cleanliness — Jimmy's exact language ---
SITE_CLEANLINESS_KEYWORDS = [
    "debris", "garbage", "waste", "swept", "shop vac",
    "roadway clean", "materials stacked", "dumpster",
    "tornado", "site cleanup", "trash", "mess",
    "job site messy", "clean up", "cleanup needed",
    "broom", "leaf blower", "dumpster needs emptying",
    "sweep", "pick up", "picked up",
    "scrap", "leftover", "sawdust", "construction waste",
    "unclean", "dirty", "filthy", "disaster",
    "unswept", "not swept", "needs cleaning",
    "scrap wood", "drywall dust", "concrete dust",
    "pack out", "packout", "haul away",
]

# --- 3. Water / moisture — Jimmy's #1 stressor, greatly expanded ---
WATER_KEYWORDS = [
    "water in basement", "sump pump", "dehumidifier",
    "fans running", "grading issue", "standing water",
    "heavy rain", "leak", "leaking", "moisture",
    "condensation", "wet", "damp", "flood",
    "water damage", "water pooling", "pump out",
    "ground water", "water intrusion", "basement wet",
    "sump", "pump failed", "sump pump failed",
    "waterproof", "waterproofing", "weeping tile",
    "drainage", "downspout", "gutter",
    "ice dam", "frost", "thaw",
    "basement flood", "crawl space wet",
    "rain water", "storm water",
]

# --- 4. Structural / load-bearing — greatly expanded from interview ---
STRUCTURAL_KEYWORDS = [
    "structural", "load bearing", "load-bearing",
    "truss", "trusses", "bearing point", "bearing wall",
    "collapsed", "collapse", "buckling",
    "inspection fail", "failed inspection",
    "framing issue", "framing error",
    "engineering", "engineer needed", "structural engineer",
    "foundation crack", "foundation settlement",
    "settlement", "settling", "frost heave",
    "concrete crack", "cracked foundation",
    "wall crack", "floor crack", "ceiling crack",
    "sinking", "shifted", "separated",
    "joist", "rafter", "beam", "header",
    "support beam", "support column",
    "sagging", "uneven floor", "uneven wall",
    "drywall crack", "corner crack", "stress crack",
    "heaving", "uplift", "foundation issue",
]

# --- 5. General Red keywords (all trades) ---
RED_KEYWORDS = [
    "issue", "emergency", "broken",
    "cannot start", "can't start", "not ready",
    "won't be there", "stop work", "shut down",
    "code violation", "safety hazard",
    "mold", "blocking", "stop", "delay",
    "major delay", "reschedule", "behind schedule",
    "not done", "not complete",
    "damage", "ruined", "destroyed",
    "redo", "rework", "rip out", "replace",
    "ordered wrong", "wrong material", "wrong size",
    "missing", "lost", "stolen",
    "fire", "smoke", "gas leak",
    "injury", "accident", "unsafe",
    "shut down", "stop work order",
    "permit issue", "permit hold",
]

# --- 6. General Yellow keywords (all trades) ---
YELLOW_KEYWORDS = [
    "partial", "almost", "running late", "behind",
    "need material", "material short", "missing piece",
    "not finished", "half done",
    "minor delay", "running behind",
    "waiting on", "waiting for",
    "shortage", "out of",
    "rescheduled", "pushed back",
    "need more time", "extra day", "extra days",
    "weather delay", "rain delay",
    "backorder", "on backorder",
    "delivery delay", "shipping delay",
    "low on", "running low",
    "mobilize", "need to mobilize",
]

# --- 7. Escalation triggers ---
ESCALATION_TRIGGERS = [
    "blocking", "can't start", "cannot start", "need immediately",
    "stopping", "prevent", "preventing", "holding up", "holding",
    "stopped work", "can't proceed", "unable to proceed",
]

# --- 8. Weather keywords (Yellow baseline, Red for foundation/framing) ---
WEATHER_KEYWORDS = [
    "weather", "rain", "snow", "ice", "wind", "cold",
    "freezing", "frozen", "frost", "storm",
    "lightning", "tornado warning", "flood warning",
    "extreme cold", "heat wave", "too hot",
]

# --- 9. Inspection-related keywords ---
INSPECTION_KEYWORDS = [
    "inspection", "inspector", "city inspector",
    "county inspector", "building department",
    "failed inspection", "pass inspection",
    "inspection scheduled", "inspection tomorrow",
    "rough in inspection", "final inspection",
    "framing inspection", "electrical inspection",
    "plumbing inspection", "mechanical inspection",
]


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result of classifying a single inbound message."""
    andon_status: str | None        # 'R', 'Y', or None (no change)
    confidence: float               # 0.0 – 1.0
    is_selections_query: bool       # If True, route to designer
    matched_keyword: str | None     # First keyword that triggered
    structured_reply: str | None    # e.g. '1', '2', '3', 'A', 'B'
    needs_review: bool = False      # If True, flag for human review
    trade_specific: bool = False    # If True, classification was trade-weighted
    matched_category: str | None = None
    hit_count: int = 0              # Number of keywords matched (multi-hit)
    severity_multiplier: float = 1.0  # Trade severity multiplier applied


# ---------------------------------------------------------------------------
# Classifier v3
# ---------------------------------------------------------------------------

class ClassifierEngine:
    """
    Trade-aware classifier v3 with multi-hit scoring.

    Usage:
        engine = ClassifierEngine()
        result = engine.classify("water in basement", trade="foundation_concrete")
        result = engine.classify("truss cracked and blocking next trade", trade="framing")
    """

    def classify(
        self,
        text: str,
        trade: str | None = None,
    ) -> ClassificationResult:
        """
        Classify an inbound message.

        Args:
            text: The raw message text from the sub.
            trade: The construction trade this message relates to.

        Returns:
            ClassificationResult with status, confidence, and metadata.
        """
        if not text or not text.strip():
            return ClassificationResult(
                andon_status=None, confidence=0.0,
                is_selections_query=False, matched_keyword=None,
                structured_reply=None, needs_review=False,
            )

        cleaned = text.strip().lower()
        is_high_risk = trade in HIGH_RISK_TRADES if trade else False
        severity = TRADE_SEVERITY.get(trade, 1.0) if trade else 1.0

        # ── Step 1: Selections query → forward to designer ──
        sel_match = self._first_match(cleaned, SELECTION_KEYWORDS)
        if sel_match:
            return ClassificationResult(
                andon_status=None, confidence=0.9,
                is_selections_query=True,
                matched_keyword=sel_match,
                structured_reply=None,
                matched_category="selections",
                severity_multiplier=severity,
            )

        # ── Step 2: Structured single-character reply ──
        st = self._parse_structured(cleaned)
        if st:
            status, confidence, matched = st
            return ClassificationResult(
                andon_status=status, confidence=confidence,
                is_selections_query=False, matched_keyword=matched,
                structured_reply=matched,
                matched_category="structured",
                severity_multiplier=severity,
            )

        # ── Step 3: Trade-specific checks ──

        # 3a: Water — foundation = Red always; framing = Red; others = Yellow
        water_match = self._first_match(cleaned, WATER_KEYWORDS)
        if water_match:
            if trade == "foundation_concrete":
                return ClassificationResult(
                    andon_status='R', confidence=min(0.95, 0.9 * severity),
                    is_selections_query=False, matched_keyword=water_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="water", severity_multiplier=severity,
                )
            elif is_high_risk:
                return ClassificationResult(
                    andon_status='R', confidence=min(0.95, 0.85 * severity),
                    is_selections_query=False, matched_keyword=water_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="water", severity_multiplier=severity,
                )
            else:
                if self._has_escalation(cleaned):
                    conf = min(0.95, 0.85 * severity)
                    return ClassificationResult(
                        andon_status='R', confidence=conf,
                        is_selections_query=False, matched_keyword=water_match,
                        structured_reply=None, trade_specific=True,
                        matched_category="water", severity_multiplier=severity,
                    )
                conf = min(0.95, 0.7 * severity)
                return ClassificationResult(
                    andon_status='Y', confidence=conf,
                    is_selections_query=False, matched_keyword=water_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="water", severity_multiplier=severity,
                )

        # 3b: Structural — Red for high-risk, Yellow for others
        struct_match = self._first_match(cleaned, STRUCTURAL_KEYWORDS)
        if struct_match:
            if is_high_risk:
                return ClassificationResult(
                    andon_status='R', confidence=min(0.99, 0.95 * severity),
                    is_selections_query=False, matched_keyword=struct_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="structural", severity_multiplier=severity,
                )
            else:
                conf = min(0.95, 0.75 * severity)
                return ClassificationResult(
                    andon_status='Y', confidence=conf,
                    is_selections_query=False, matched_keyword=struct_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="structural", severity_multiplier=severity,
                )

        # 3c: Site cleanliness — Yellow baseline, Red if blocking
        clean_match = self._first_match(cleaned, SITE_CLEANLINESS_KEYWORDS)
        if clean_match:
            if self._has_escalation(cleaned):
                return ClassificationResult(
                    andon_status='R', confidence=0.85,
                    is_selections_query=False, matched_keyword=clean_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="cleanliness", severity_multiplier=severity,
                )
            conf = 0.75 if is_high_risk else 0.65
            return ClassificationResult(
                andon_status='Y', confidence=conf,
                is_selections_query=False, matched_keyword=clean_match,
                structured_reply=None, trade_specific=True,
                matched_category="cleanliness", severity_multiplier=severity,
            )

        # 3d: Weather — Yellow for most trades, Red for foundation
        weather_match = self._first_match(cleaned, WEATHER_KEYWORDS)
        if weather_match:
            if trade == "foundation_concrete":
                return ClassificationResult(
                    andon_status='R', confidence=0.8,
                    is_selections_query=False, matched_keyword=weather_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="weather", severity_multiplier=severity,
                )
            return ClassificationResult(
                andon_status='Y', confidence=0.6,
                is_selections_query=False, matched_keyword=weather_match,
                structured_reply=None, trade_specific=True,
                matched_category="weather", severity_multiplier=severity,
            )

        # 3e: Inspection issues — Red for structural inspections, Yellow for finish
        insp_match = self._first_match(cleaned, INSPECTION_KEYWORDS)
        if insp_match:
            if is_high_risk and ("fail" in cleaned or "issue" in cleaned):
                return ClassificationResult(
                    andon_status='R', confidence=0.9,
                    is_selections_query=False, matched_keyword=insp_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="inspection", severity_multiplier=severity,
                )
            if "fail" in cleaned:
                return ClassificationResult(
                    andon_status='Y', confidence=0.7,
                    is_selections_query=False, matched_keyword=insp_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="inspection", severity_multiplier=severity,
                )

        # ── Step 3f: Graded keywords from Excel checklist ──
        # These are user-curated Red/Yellow terms per trade from the
        # keywords_and_phrases_checklist.xlsx file. They take priority
        # over the built-in general lists.
        trade_key = _trade_to_sheet_name(trade) if trade else None
        if trade_key:
            graded_red, graded_yellow = get_graded_keywords(trade_key)
            g_red_match = self._first_match(cleaned, graded_red)
            if g_red_match:
                return ClassificationResult(
                    andon_status='R', confidence=min(0.95, 0.85 * severity),
                    is_selections_query=False, matched_keyword=g_red_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="graded_red", severity_multiplier=severity,
                )
            g_yellow_match = self._first_match(cleaned, graded_yellow)
            if g_yellow_match:
                conf = min(0.9, 0.65 * severity)
                return ClassificationResult(
                    andon_status='Y', confidence=conf,
                    is_selections_query=False, matched_keyword=g_yellow_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="graded_yellow", severity_multiplier=severity,
                )

        # ── Step 4: Multi-hit scoring for Red keywords ──
        red_hits = self._count_matches(cleaned, RED_KEYWORDS)
        if red_hits >= 2:
            # Multiple Red keywords = very confident
            conf = min(0.99, (0.8 + (red_hits - 1) * 0.1) * severity)
            return ClassificationResult(
                andon_status='R', confidence=conf,
                is_selections_query=False,
                matched_keyword=f"{red_hits}x_red_keywords",
                structured_reply=None, hit_count=red_hits,
                matched_category="general", severity_multiplier=severity,
            )
        if red_hits == 1:
            conf = min(0.95, 0.8 * severity)
            return ClassificationResult(
                andon_status='R', confidence=conf,
                is_selections_query=False,
                matched_keyword=self._first_match(cleaned, RED_KEYWORDS),
                structured_reply=None, hit_count=1,
                matched_category="general", severity_multiplier=severity,
            )

        # ── Step 5: Multi-hit scoring for Yellow keywords ──
        yellow_hits = self._count_matches(cleaned, YELLOW_KEYWORDS)
        if yellow_hits >= 3:
            # 3+ Yellow keywords → upgrade to Red (too many flags)
            conf = min(0.95, 0.75 * severity)
            return ClassificationResult(
                andon_status='R', confidence=conf,
                is_selections_query=False,
                matched_keyword=f"{yellow_hits}x_yellow_upgrade",
                structured_reply=None, hit_count=yellow_hits,
                matched_category="general", severity_multiplier=severity,
            )
        if yellow_hits >= 1:
            conf = min(0.9, 0.6 * severity)
            return ClassificationResult(
                andon_status='Y', confidence=conf,
                is_selections_query=False,
                matched_keyword=self._first_match(cleaned, YELLOW_KEYWORDS),
                structured_reply=None, hit_count=yellow_hits,
                matched_category="general", severity_multiplier=severity,
            )

        # ── Step 6: Low confidence / ambiguous ──
        if self._looks_ambiguous(cleaned):
            return ClassificationResult(
                andon_status=None, confidence=0.25,
                is_selections_query=False, matched_keyword=None,
                structured_reply=None, needs_review=True,
                matched_category="ambiguous", severity_multiplier=severity,
            )

        # ── Nothing matched ──
        return ClassificationResult(
            andon_status=None, confidence=0.2 * severity,
            is_selections_query=False, matched_keyword=None,
            structured_reply=None, needs_review=False,
            severity_multiplier=severity,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_selections(text: str) -> bool:
        return any(kw in text for kw in SELECTION_KEYWORDS)

    @staticmethod
    def _has_escalation(text: str) -> bool:
        return any(trig in text for trig in ESCALATION_TRIGGERS)

    @staticmethod
    def _count_matches(text: str, keywords: list[str]) -> int:
        """Count how many keywords match the text (multi-hit scoring)."""
        return sum(1 for kw in keywords if kw in text)

    @staticmethod
    def _looks_ambiguous(text: str) -> bool:
        """
        Detect messages that are about the job but didn't match
        known keywords. V3: uses topic clusters for better detection.
        """
        job_indicators = [
            "job", "site", "house", "trade", "work", "today",
            "tomorrow", "this week", "problem", "need", "here",
        ]
        words = text.split()
        # Substantial message (3+ words) with job indicators
        if len(words) >= 3:
            if any(ind in text for ind in job_indicators):
                return True
        # Messages with question marks or exclamation marks about work
        if len(text) > 30 and any(c in text for c in ["?", "!", ".."]):
            return True
        # Single-word status updates that aren't structured replies
        if len(words) <= 2 and len(text) > 5:
            single_words = {"ok", "okay", "kk", "got it", "roger", "copy",
                           "thanks", "thank you", "np", "no problem", "sounds good"}
            if text not in single_words:
                return True
        return False

    @staticmethod
    def _parse_structured(
        text: str,
    ) -> tuple[str, float, str] | None:
        """Parse known structured replies."""
        text = text.strip().lower()

        if text.startswith("issue"):
            return ('R', 0.95, 'issue_prefix')

        single_char_map = {
            '1': ('G', 0.98, '1'),
            '2': ('Y', 0.95, '2'),
            '3': ('R', 0.95, '3'),
            'a': ('G', 0.85, 'A'),
            'b': ('Y', 0.85, 'B'),
        }
        if text in single_char_map:
            return single_char_map[text]

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
