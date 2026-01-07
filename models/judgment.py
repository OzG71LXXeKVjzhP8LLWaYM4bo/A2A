"""Judgment and quality scoring models for the question pipeline."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, computed_field


class JudgmentStatus(str, Enum):
    """Final judgment status for a question."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class DifficultyAssessment(BaseModel):
    """Assessment of question difficulty."""
    assessed_difficulty: int  # 1-3
    target_difficulty: int  # What was requested
    matches_target: bool
    reasoning: str  # Why this difficulty level
    cognitive_load: str  # "low", "medium", "high"
    steps_required: int  # Estimated solution steps
    time_estimate_seconds: int


class ClarityAssessment(BaseModel):
    """Assessment of question clarity."""
    clarity_score: float  # 0-1
    is_unambiguous: bool
    grammar_correct: bool
    age_appropriate: bool  # For Year 6 students
    issues: list[str] = []


class AlignmentAssessment(BaseModel):
    """Assessment of curriculum alignment."""
    alignment_score: float  # 0-1
    matches_concept: bool
    matches_subtopic: bool
    tests_intended_skill: bool
    issues: list[str] = []


class NoveltyAssessment(BaseModel):
    """Assessment of question novelty (for deduplication)."""
    novelty_score: float  # 0-1, 1 = completely novel
    similar_question_ids: list[UUID] = []
    max_similarity: float = 0.0
    is_duplicate: bool = False


class JudgmentScores(BaseModel):
    """All quality scores for a question."""
    # Core scores
    difficulty_assessment: DifficultyAssessment
    clarity_assessment: ClarityAssessment
    alignment_assessment: AlignmentAssessment

    # Solver verification
    solver_verified: bool = False
    solver_confidence: float = 0.0
    solver_found_ambiguity: bool = False

    # Adversarial robustness
    adversarial_robustness: float = 0.0
    adversarial_passed: bool = False

    # Optional novelty (when embeddings enabled)
    novelty_assessment: Optional[NoveltyAssessment] = None

    @computed_field
    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score."""
        weights = {
            "difficulty": 0.15,
            "clarity": 0.25,
            "alignment": 0.20,
            "solver": 0.20,
            "adversarial": 0.20,
        }

        difficulty_score = 1.0 if self.difficulty_assessment.matches_target else 0.5
        clarity_score = self.clarity_assessment.clarity_score
        alignment_score = self.alignment_assessment.alignment_score
        solver_score = self.solver_confidence if self.solver_verified else 0.0
        adversarial_score = self.adversarial_robustness

        return (
            weights["difficulty"] * difficulty_score +
            weights["clarity"] * clarity_score +
            weights["alignment"] * alignment_score +
            weights["solver"] * solver_score +
            weights["adversarial"] * adversarial_score
        )


class JudgmentResult(BaseModel):
    """Final judgment result for a question."""
    question_id: UUID
    question_preview: str  # First 100 chars

    # Scores
    scores: JudgmentScores

    # Thresholds (configurable)
    min_overall_score: float = 0.7
    min_clarity_score: float = 0.8
    min_solver_confidence: float = 0.9
    min_adversarial_robustness: float = 0.7

    # Final decision
    status: JudgmentStatus
    rejection_reasons: list[str] = []
    revision_suggestions: list[str] = []

    @computed_field
    @property
    def passed(self) -> bool:
        """Check if question passed all thresholds."""
        return self.status == JudgmentStatus.ACCEPTED

    def check_thresholds(self) -> tuple[bool, list[str]]:
        """Check all quality thresholds and return pass/fail with reasons."""
        reasons = []

        if self.scores.overall_score < self.min_overall_score:
            reasons.append(f"Overall score {self.scores.overall_score:.2f} below threshold {self.min_overall_score}")

        if self.scores.clarity_assessment.clarity_score < self.min_clarity_score:
            reasons.append(f"Clarity score {self.scores.clarity_assessment.clarity_score:.2f} below threshold {self.min_clarity_score}")

        if self.scores.solver_confidence < self.min_solver_confidence:
            reasons.append(f"Solver confidence {self.scores.solver_confidence:.2f} below threshold {self.min_solver_confidence}")

        if self.scores.adversarial_robustness < self.min_adversarial_robustness:
            reasons.append(f"Adversarial robustness {self.scores.adversarial_robustness:.2f} below threshold {self.min_adversarial_robustness}")

        if self.scores.solver_found_ambiguity:
            reasons.append("Solver detected ambiguity in question")

        passed = len(reasons) == 0
        return passed, reasons


class PipelineResult(BaseModel):
    """Result of the full question generation pipeline."""
    accepted: bool
    question: Optional[Any] = None  # Question model
    concept_id: Optional[str] = None
    revision_count: int = 0
    judgment: Optional[dict] = None
    errors: list[str] = []

    @property
    def success(self) -> bool:
        return self.accepted and self.question is not None
