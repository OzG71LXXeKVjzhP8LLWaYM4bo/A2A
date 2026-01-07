"""Question and Exam data models supporting all question types."""

from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class QuestionTypeEnum(str, Enum):
    """All supported question types matching database schema."""
    MULTIPLE_CHOICE = "multiple-choice"
    MULTIPLE_CHOICE_WITH_IMAGES = "multiple-choice-with-images"
    DRAG_AND_DROP = "drag-and-drop"
    MULTI_SUBQUESTION = "multi-subquestion"
    CLOZE = "cloze"
    WRITING = "writing"


class Choice(BaseModel):
    """Universal Choice interface - fields used depend on question type.

    For MCQ: id, text, is_correct (bool)
    For MCQ with images: id, text, is_correct (bool), image (URL)
    For drag-and-drop: id, text, correct_position (int or null for distractor)
    For multi-subquestion: id, text (the subquestion), correct (letter A/B/C)
    For cloze: id, text="", options (4 strings), is_correct (0-3 index)
    """
    id: str
    text: str

    # MCQ fields
    is_correct: Optional[Union[bool, int]] = None  # bool for MCQ, int 0-3 for cloze

    # MCQ with images
    image: Optional[str] = None  # URL to image

    # Drag-and-drop fields
    correct_position: Optional[int] = None  # 1-indexed position, null = distractor

    # Multi-subquestion fields
    correct: Optional[str] = None  # Letter (A, B, C...) for correct extract

    # Cloze fields
    options: Optional[list[str]] = None  # Exactly 4 options for dropdown


class MarkingCriterion(BaseModel):
    """Marking criterion for writing questions."""
    id: str
    name: str
    max_marks: int
    description: str


class Question(BaseModel):
    """Complete question data structure supporting all types."""
    id: UUID = Field(default_factory=uuid4)

    # Content fields
    content: Optional[str] = None  # Main passage/context, or cloze template with {{N}}
    question: str  # The actual question text
    explanation: str = ""

    # Type and difficulty
    type: str = QuestionTypeEnum.MULTIPLE_CHOICE.value
    difficulty: str = "2"  # 1-5 scale as string

    # Topic/subtopic references
    topic_id: Optional[UUID] = None
    subtopic_id: Optional[UUID] = None
    subtopic_ids: list[UUID] = []  # Array for multiple subtopics
    subtopic_name: str = ""

    # Choices - structure varies by type
    choices: Optional[list[Choice]] = []

    # For drag-and-drop
    max_positions: Optional[int] = None  # Number of slots to fill

    # For multi-subquestion - references to extracts table
    extract_id: Optional[list[UUID]] = None

    # For writing questions
    marking_criteria: list[MarkingCriterion] = []

    # Image support
    requires_image: bool = False
    image_description: Optional[str] = None
    image_url: Optional[str] = None

    # Metadata
    tags: list[str] = []
    showup: bool = True
    is_active: bool = True

    # Analytics fields (read from DB)
    most_common_choice: Optional[dict] = None
    percent_correct: Optional[float] = None
    total_attempts: int = 0

    @property
    def correct_choice(self) -> Optional[Choice]:
        """Get the correct choice for MCQ types."""
        if self.type in [QuestionTypeEnum.MULTIPLE_CHOICE.value,
                         QuestionTypeEnum.MULTIPLE_CHOICE_WITH_IMAGES.value]:
            for choice in self.choices or []:
                if choice.is_correct is True:
                    return choice
        return None

    @property
    def correct_order(self) -> list[str]:
        """Get correct order for drag-and-drop questions."""
        if self.type != QuestionTypeEnum.DRAG_AND_DROP.value:
            return []
        return [
            c.id for c in sorted(
                [c for c in (self.choices or []) if c.correct_position is not None],
                key=lambda x: x.correct_position or 0
            )
        ]

    def validate_structure(self) -> list[str]:
        """Validate question structure based on type."""
        errors = []

        if not self.question.strip():
            errors.append("Question text is required")

        if self.type == QuestionTypeEnum.MULTIPLE_CHOICE.value:
            errors.extend(self._validate_mcq())
        elif self.type == QuestionTypeEnum.MULTIPLE_CHOICE_WITH_IMAGES.value:
            errors.extend(self._validate_mcq_images())
        elif self.type == QuestionTypeEnum.DRAG_AND_DROP.value:
            errors.extend(self._validate_drag_drop())
        elif self.type == QuestionTypeEnum.MULTI_SUBQUESTION.value:
            errors.extend(self._validate_multi_sub())
        elif self.type == QuestionTypeEnum.CLOZE.value:
            errors.extend(self._validate_cloze())
        elif self.type == QuestionTypeEnum.WRITING.value:
            errors.extend(self._validate_writing())

        return errors

    def _validate_mcq(self) -> list[str]:
        """Validate multiple choice question."""
        errors = []
        if not self.choices or len(self.choices) < 2:
            errors.append("At least 2 choices required")
        else:
            correct_count = sum(1 for c in self.choices if c.is_correct is True)
            if correct_count != 1:
                errors.append(f"Exactly one correct answer required, found {correct_count}")
        return errors

    def _validate_mcq_images(self) -> list[str]:
        """Validate MCQ with images."""
        errors = self._validate_mcq()
        if self.choices:
            for i, c in enumerate(self.choices):
                if not c.image:
                    errors.append(f"Choice {i+1} missing image URL")
        return errors

    def _validate_drag_drop(self) -> list[str]:
        """Validate drag-and-drop question."""
        errors = []
        if not self.choices or len(self.choices) < 2:
            errors.append("At least 2 items required")
        else:
            valid_positions = [c for c in self.choices if c.correct_position is not None]
            if len(valid_positions) < 2:
                errors.append("At least 2 items with positions required")

            # Check positions are sequential starting at 1
            positions = sorted([c.correct_position for c in valid_positions])
            expected = list(range(1, len(positions) + 1))
            if positions != expected:
                errors.append(f"Positions must be sequential from 1, got {positions}")

            if self.max_positions and self.max_positions != len(valid_positions):
                errors.append(f"max_positions ({self.max_positions}) doesn't match valid items ({len(valid_positions)})")
        return errors

    def _validate_multi_sub(self) -> list[str]:
        """Validate multi-subquestion."""
        errors = []
        if not self.choices:
            errors.append("At least one subquestion required")
        else:
            for i, c in enumerate(self.choices):
                if not c.correct:
                    errors.append(f"Subquestion {i+1} missing correct answer letter")
                elif not c.correct.isalpha() or len(c.correct) != 1:
                    errors.append(f"Subquestion {i+1} correct must be single letter (A/B/C)")

        if not self.extract_id:
            errors.append("extract_id array required for multi-subquestion")
        return errors

    def _validate_cloze(self) -> list[str]:
        """Validate cloze question."""
        errors = []
        if not self.choices:
            errors.append("At least one blank required")
        else:
            for i, c in enumerate(self.choices):
                if not c.options or len(c.options) != 4:
                    errors.append(f"Blank {i+1} must have exactly 4 options")
                if not isinstance(c.is_correct, int) or c.is_correct < 0 or c.is_correct > 3:
                    errors.append(f"Blank {i+1} is_correct must be 0-3")

        # Check placeholders in content match choice IDs
        if self.content:
            for c in self.choices or []:
                placeholder = f"{{{{{c.id}}}}}"
                if placeholder not in self.content:
                    errors.append(f"Placeholder {placeholder} not found in content")
        return errors

    def _validate_writing(self) -> list[str]:
        """Validate writing question."""
        errors = []
        if self.choices is not None and len(self.choices) > 0:
            errors.append("Writing questions must have null/empty choices")
        if not self.marking_criteria:
            errors.append("Writing questions require marking_criteria")
        else:
            for i, mc in enumerate(self.marking_criteria):
                if not mc.id or not mc.name or mc.max_marks <= 0:
                    errors.append(f"Marking criterion {i+1} invalid")
        return errors


class Exam(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    code: str
    name: str
    description: str = ""
    type: str = "thinking-skills"
    time_limit: int = 45
    question_count: int = 0
    topic_id: Optional[UUID] = None
    questions: list[Question] = []
    is_active: bool = True


class ExamConfig(BaseModel):
    exam_code: Optional[str] = None
    exam_name: Optional[str] = None
    exam_description: str = ""
    time_limit: int = 45
    enable_images: bool = True
    custom_instructions: str = ""


class ThinkingSkillsConfig(ExamConfig):
    # 8 subtopics matching n8n and database
    analogies_count: int = 4
    critical_thinking_count: int = 4
    deduction_count: int = 5
    inference_count: int = 4
    logical_reasoning_count: int = 5
    pattern_recognition_count: int = 5
    sequencing_count: int = 4
    spatial_reasoning_count: int = 4


class MathConfig(ExamConfig):
    averages_count: int = 3
    fractions_count: int = 4
    geometry_count: int = 5
    measurement_count: int = 4
    number_patterns_count: int = 3
    percentages_count: int = 4
    probability_count: int = 3
    problem_solving_count: int = 5
    ratios_count: int = 4
    statistics_count: int = 4
