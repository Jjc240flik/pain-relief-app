"""
ClassifierEngine v2 — Trade-aware, multi-dimension keyword classification.

Improvements over v1:
  - Accepts optional trade context for per-trade severity weighting
  - Site cleanliness detection (from Jimmy's interview language)
  - Water/moisture detection with trade-aware escalation
  - Structural severity weighting (Framing / Foundation get stricter)
  - Low-confidence / ambiguous message flagging
  - Expanded selections detection
  - ClassificationResult now includes needs_review and trade_specific flags

Pipeline order:
  1. Selection keyword check        (→ forward to designer)
  2. Structured single-char reply   (1/2/3/A/B — highest confidence)
  3. Trade-specific checks          (framing, foundation get special treatment)
  4. General Red keywords           (all trades)
  5. General Yellow keywords        (all trades)
  6. Low confidence / ambiguous     (→ needs_review=True, no status change)

Operational language sourced from:
  - Jimmy's full interview transcript (site walks, weather, sub friction)
  - PRD definitions of Red / Yellow
  - Common construction SMS patterns observed in field testing
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Trade phase identifiers
# ---------------------------------------------------------------------------

HIGH_RISK_TRADES = {"foundation_concrete", "framing"}

TRADE_PHASES = [
    "foundation_concrete", "framing", "plumbing_rough", "hvac_rough",
    "electrical_rough", "drywall_plaster", "paint", "flooring",
    "cabinets", "finish_work",
]

# ---------------------------------------------------------------------------
# Keyword lists — organised by category
# ---------------------------------------------------------------------------

# --- 1. Selections / finishes — forward to designer (no status change) ---
# Expanded from interview: Jimmy's biggest info gap was interior selections
SELECTION_KEYWORDS = [
    "paint", "color", "finish", "selection", "what color",
    "hardware", "fixture", "countertop", "cabinet color",
    "floor color", "trim color", "door style", "what shade",
    "what colour", "cabinet style", "counter material",
    "backsplash", "appliance color", "light fixture",
    "faucet style", "door handle", "tile color",
    "what finish", "what stain", "what flooring",
]

# --- 2. Site cleanliness — from Jimmy's interview language ---
# Jimmy: "walk up to a job site and it looks like a tornado went through"
# Jimmy: "nobody wants to do... gets pushed off to the next trade"
# Jimmy: "basic overall cleanliness"
SITE_CLEANLINESS_KEYWORDS = [
    "debris", "garbage", "waste", "swept", "shop vac",
    "roadway clean", "materials stacked", "dumpster",
    "tornado", "site cleanup", "trash", "mess",
    "job site messy", "clean up", "cleanup needed",
    "broom", "leaf blower", "dumpster needs emptying",
    "sweep", "pick up", "picked up",
    "scrap", "leftover", "sawdust", "construction waste",
]

# --- 3. Water / moisture — Jimmy's #1 stressor ---
# Jimmy: "Water and home building do not mix"
# Jimmy: "Everything that comes with water"
# Jimmy: "water in the basement... peeling up and drying on floors"
WATER_KEYWORDS = [
    "water in basement", "sump pump", "dehumidifier",
    "fans running", "grading issue", "standing water",
    "heavy rain", "leak", "leaking", "moisture",
    "condensation", "wet", "damp", "flood",
    "water damage", "water pooling", "pump out",
    "ground water", "water intrusion", "basement wet",
    "sump", "pump failed",
]

# --- 4. Structural / load-bearing — critical for framing & foundation ---
# Jimmy: "the bones of the house"
# Jimmy: "structural, engineering, inspection failure issues escalate"
STRUCTURAL_KEYWORDS = [
    "structural", "load bearing", "load-bearing",
    "truss", "trusses", "bearing point",
    "collapsed", "collapse", "buckling",
    "inspection fail", "failed inspection",
    "framing issue", "framing error",
    "engineering", "engineer needed",
    "foundation crack", "foundation settlement",
    "settlement", "settling", "frost heave",
    "concrete crack", "cracked foundation",
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
]

# --- 6. General Yellow keywords (all trades) ---
YELLOW_KEYWORDS = [
    "partial", "almost", "running late", "behind",
    "need material", "material short", "missing piece",
    "not finished", "half done",
    "minor delay", "running behind",
    "waiting on", "waiting for",
    "shortage", "out of",
]

# --- 7. Escalation triggers — when paired with other keywords, upgrade to Red ---
ESCALATION_TRIGGERS = [
    "blocking", "can't start", "cannot start", "need immediately",
    "stopping", "prevent", "preventing",
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
    matched_category: str | None = None  # Which category triggered: 'cleanliness', 'water', 'structural', 'general'


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class ClassifierEngine:
    """
    Trade-aware, multi-dimension keyword classifier.

    Usage:
        engine = ClassifierEngine()
        result = engine.classify("water in basement", trade="foundation_concrete")
        result = engine.classify("2")  # structured reply, no trade needed
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
            trade: The construction trade this message relates to
                   (e.g. 'framing', 'foundation_concrete'). Optional.

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

        # ── Step 1: Selections query → forward to designer ──
        sel_match = self._first_match(cleaned, SELECTION_KEYWORDS)
        if sel_match:
            return ClassificationResult(
                andon_status=None, confidence=0.9,
                is_selections_query=True,
                matched_keyword=sel_match,
                structured_reply=None,
                matched_category="selections",
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
            )

        # ── Step 3: Trade-specific checks ──
        is_high_risk = trade in HIGH_RISK_TRADES if trade else False

        # 3a: Water / moisture — especially critical for foundation
        water_match = self._first_match(cleaned, WATER_KEYWORDS)
        if water_match:
            if trade == "foundation_concrete":
                # Water in foundation = Red, high confidence
                return ClassificationResult(
                    andon_status='R', confidence=0.9,
                    is_selections_query=False, matched_keyword=water_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="water",
                )
            elif is_high_risk:
                # Water during framing = Red (structural risk from moisture)
                return ClassificationResult(
                    andon_status='R', confidence=0.85,
                    is_selections_query=False, matched_keyword=water_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="water",
                )
            else:
                # Water in other trades = Yellow (unless paired with escalation)
                if self._has_escalation(cleaned):
                    return ClassificationResult(
                        andon_status='R', confidence=0.8,
                        is_selections_query=False, matched_keyword=water_match,
                        structured_reply=None, trade_specific=True,
                        matched_category="water",
                    )
                return ClassificationResult(
                    andon_status='Y', confidence=0.7,
                    is_selections_query=False, matched_keyword=water_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="water",
                )

        # 3b: Structural keywords — Red for high-risk trades, Yellow for others
        struct_match = self._first_match(cleaned, STRUCTURAL_KEYWORDS)
        if struct_match:
            if is_high_risk:
                return ClassificationResult(
                    andon_status='R', confidence=0.95,
                    is_selections_query=False, matched_keyword=struct_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="structural",
                )
            else:
                # Still concerning for any trade
                return ClassificationResult(
                    andon_status='Y', confidence=0.7,
                    is_selections_query=False, matched_keyword=struct_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="structural",
                )

        # 3c: Site cleanliness — Yellow baseline, Red if blocking next trade
        clean_match = self._first_match(cleaned, SITE_CLEANLINESS_KEYWORDS)
        if clean_match:
            if self._has_escalation(cleaned):
                return ClassificationResult(
                    andon_status='R', confidence=0.85,
                    is_selections_query=False, matched_keyword=clean_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="cleanliness",
                )
            # Also escalate if framing/foundation — cleanliness is critical early on
            if is_high_risk:
                return ClassificationResult(
                    andon_status='Y', confidence=0.75,
                    is_selections_query=False, matched_keyword=clean_match,
                    structured_reply=None, trade_specific=True,
                    matched_category="cleanliness",
                )
            return ClassificationResult(
                andon_status='Y', confidence=0.65,
                is_selections_query=False, matched_keyword=clean_match,
                structured_reply=None, trade_specific=True,
                matched_category="cleanliness",
            )

        # ── Step 4: General Red keywords ──
        red_match = self._first_match(cleaned, RED_KEYWORDS)
        if red_match:
            conf = 0.85 if is_high_risk else 0.75
            return ClassificationResult(
                andon_status='R', confidence=conf,
                is_selections_query=False, matched_keyword=red_match,
                structured_reply=None, matched_category="general",
            )

        # ── Step 5: General Yellow keywords ──
        yellow_match = self._first_match(cleaned, YELLOW_KEYWORDS)
        if yellow_match:
            return ClassificationResult(
                andon_status='Y', confidence=0.6,
                is_selections_query=False, matched_keyword=yellow_match,
                structured_reply=None, matched_category="general",
            )

        # ── Step 6: Low confidence / ambiguous ──
        # The message didn't trigger any known pattern.
        # If it looks like a complaint or status update, flag for review.
        if self._looks_ambiguous(cleaned):
            return ClassificationResult(
                andon_status=None, confidence=0.25,
                is_selections_query=False, matched_keyword=None,
                structured_reply=None, needs_review=True,
                matched_category="ambiguous",
            )

        # ── Nothing matched ──
        return ClassificationResult(
            andon_status=None, confidence=0.2,
            is_selections_query=False, matched_keyword=None,
            structured_reply=None, needs_review=False,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_selections(text: str) -> bool:
        return any(kw in text for kw in SELECTION_KEYWORDS)

    @staticmethod
    def _has_escalation(text: str) -> bool:
        """Check if message contains escalation triggers that upgrade to Red."""
        return any(trig in text for trig in ESCALATION_TRIGGERS)

    @staticmethod
    def _looks_ambiguous(text: str) -> bool:
        """
        Detect messages that are probably about the job but didn't match
        any known keyword pattern. These should be flagged for human review.

        Heuristics: contains job-related words, is longer than a few chars,
        but didn't match any keyword list.
        """
        job_indicators = [
            "job", "site", "house", "trade", "work", "today",
            "tomorrow", "this week", "problem", "need", "here",
        ]
        # If it's a substantial message (3+ words) with job indicators
        words = text.split()
        if len(words) >= 3:
            if any(ind in text for ind in job_indicators):
                return True
        # Long single messages that seem like complaints
        if len(text) > 40 and any(c in text for c in ["?", "!", ".."]):
            return True
        return False

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

        # "ISSUE <description>" — always Red (PRD mandate)
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

        # Word-level replies
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
