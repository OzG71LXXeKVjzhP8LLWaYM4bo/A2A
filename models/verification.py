"""Verification result models for the VerifierAgent."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class VerificationStatus(str, Enum):
    """Simple pass/fail status for verification."""
    PASS = "pass"
    FAIL = "fail"


class VerificationIssue(BaseModel):
    """A single issue found during verification."""
    category: str  # "answer", "quality", "format", "explanation"
    message: str
    suggestion: Optional[str] = None


class QuestionVerification(BaseModel):
    """Verification result for a single question."""
    question_id: Optional[str] = None
    question_text: str  # First 100 chars for identification
    status: VerificationStatus

    # Individual check results
    answer_correct: bool
    answer_confidence: float  # 0.0 to 1.0
    verified_correct_choice: Optional[str] = None  # The choice ID verifier determined

    quality_ok: bool
    format_ok: bool
    explanation_ok: bool

    issues: list[VerificationIssue] = []

    @property
    def passed(self) -> bool:
        return self.status == VerificationStatus.PASS


class BatchVerificationResult(BaseModel):
    """Verification results for a batch of questions."""
    total_questions: int
    passed: int
    failed: int

    questions: list[QuestionVerification]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_questions if self.total_questions > 0 else 0.0

    @property
    def all_passed(self) -> bool:
        return self.failed == 0
