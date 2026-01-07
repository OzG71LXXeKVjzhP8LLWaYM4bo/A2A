"""Blueprint models for structured question planning."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Type of question to generate - matches database schema."""
    MCQ = "multiple-choice"
    MCQ_IMAGES = "multiple-choice-with-images"
    DRAG_AND_DROP = "drag-and-drop"
    MULTI_SUBQUESTION = "multi-subquestion"
    CLOZE = "cloze"
    WRITING = "writing"


class TargetSkill(str, Enum):
    """Target cognitive skill for the question."""
    RECALL = "recall"  # Direct memory retrieval
    APPLICATION = "application"  # Apply known concepts to new situations
    TRANSFER = "transfer"  # Apply concepts across domains
    ANALYSIS = "analysis"  # Break down and examine relationships


class DistractorSpec(BaseModel):
    """Specification for a distractor (wrong answer) in an MCQ."""
    id: str  # "1", "2", "3", or "4"
    misconception: str  # What error or misconception leads to this answer
    error_type: str  # "calculation", "conceptual", "procedural", "misread"
    text_hint: Optional[str] = None  # Hint for how to phrase this distractor
    plausibility_score: float = 0.5  # 0-1, how plausible this distractor is


class SolutionStep(BaseModel):
    """A step in the solution path."""
    step_number: int
    description: str  # What this step does
    operation: Optional[str] = None  # Mathematical/logical operation
    intermediate_result: Optional[Any] = None  # Result after this step
    reasoning: str  # Why this step is needed


class QuestionBlueprint(BaseModel):
    """
    Structured blueprint for a question before natural language generation.

    This captures the logical structure, intended distractors, and solution
    path before the Surface Realiser converts it to actual question text.
    """
    id: UUID = Field(default_factory=uuid4)

    # Source concept
    concept_id: str
    concept_name: str
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID

    # Question specification
    question_type: QuestionType = QuestionType.MCQ
    target_skill: TargetSkill = TargetSkill.APPLICATION
    difficulty_target: int = 3  # 1-3 (1=easy, 2=medium, 3=hard)

    # Content structure
    setup_elements: list[str] = []  # Facts, context, scenario elements
    question_stem_structure: str  # Template/structure for the question
    constraints: list[str] = []  # Logical constraints that must hold

    # Answer specification
    correct_answer_value: Any  # The actual correct answer
    correct_answer_reasoning: str  # Why this is correct

    # Distractors (for MCQ)
    distractors: list[DistractorSpec] = []

    # Solution path
    solution_steps: list[SolutionStep] = []
    estimated_solve_time_seconds: int = 60

    # Image requirements
    requires_image: bool = False
    image_spec: Optional[str] = None  # Description for image generation
    image_type: Optional[str] = None  # "diagram", "chart", "portrait", etc.

    # Metadata
    tags: list[str] = []
    revision_count: int = 0
    revision_feedback: list[str] = []  # Feedback from failed attempts


class BlueprintRevision(BaseModel):
    """Request to revise a blueprint based on feedback."""
    original_blueprint: QuestionBlueprint
    issues: list[str]  # What went wrong
    suggestions: list[str]  # How to fix it
    revision_type: str  # "distractor", "ambiguity", "difficulty", "clarity"
