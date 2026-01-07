"""Adversarial testing models for question quality assurance."""

from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AttackType(str, Enum):
    """Types of adversarial attacks on a question."""
    SHORTCUT = "shortcut"  # Can answer without intended reasoning
    AMBIGUITY = "ambiguity"  # Multiple valid interpretations
    ELIMINATION = "elimination"  # Can eliminate to correct answer too easily
    PATTERN_EXPLOIT = "pattern_exploit"  # Answer follows predictable pattern
    GUESSING = "guessing"  # Random guessing gives good odds
    KEYWORD_MATCHING = "keyword_matching"  # Can match keywords to answer
    LENGTH_BIAS = "length_bias"  # Correct answer differs in length
    GRAMMAR_CLUE = "grammar_clue"  # Grammar gives away the answer


class Severity(str, Enum):
    """Severity of an issue found."""
    CRITICAL = "critical"  # Question is fundamentally broken
    MAJOR = "major"  # Significant quality issue
    MINOR = "minor"  # Small improvement possible
    INFO = "info"  # Observation, not necessarily a problem


class AdversarialAttack(BaseModel):
    """A specific attack or exploit found in a question."""
    attack_type: AttackType
    severity: Severity
    description: str  # What the attack/exploit is
    exploit_method: str  # How a student could use this
    example: Optional[str] = None  # Example of the exploit in action
    suggested_fix: Optional[str] = None  # How to fix this issue


class AdversarialReport(BaseModel):
    """Complete adversarial analysis report for a question."""
    question_id: UUID
    question_preview: str  # First 100 chars of question

    # Attacks found
    attacks: list[AdversarialAttack] = []

    # Overall assessment
    overall_robustness: float  # 0-1, 1 = no exploits found
    needs_revision: bool = False

    # Feedback for revision
    critical_issues: list[str] = []  # Must fix
    major_issues: list[str] = []  # Should fix
    minor_issues: list[str] = []  # Nice to fix

    # Revision suggestions for the Planner
    revision_suggestions: list[str] = []

    @property
    def has_critical_issues(self) -> bool:
        """Check if any critical issues were found."""
        return any(a.severity == Severity.CRITICAL for a in self.attacks)

    @property
    def pass_threshold(self) -> bool:
        """Check if question passes adversarial testing."""
        return not self.has_critical_issues and self.overall_robustness >= 0.7


class ShortcutAnalysis(BaseModel):
    """Analysis of potential shortcuts in a question."""
    shortcut_found: bool
    shortcut_description: Optional[str] = None
    shortcut_success_rate: float = 0.0  # Estimated success rate using shortcut
    intended_reasoning_required: bool = True


class AmbiguityAnalysis(BaseModel):
    """Analysis of potential ambiguities in a question."""
    is_ambiguous: bool
    ambiguity_type: Optional[str] = None  # "wording", "interpretation", "scope"
    alternative_interpretations: list[str] = []
    clarification_needed: Optional[str] = None
