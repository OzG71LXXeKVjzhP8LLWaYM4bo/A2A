"""Question and Exam data models."""

from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class Choice(BaseModel):
    id: str
    text: str
    is_correct: bool = False


class Question(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content: Optional[str] = None
    question: str
    choices: list[Choice]
    explanation: str
    difficulty: str = "2"
    subtopic_id: Optional[UUID] = None
    subtopic_name: str
    requires_image: bool = False
    image_description: Optional[str] = None
    image_url: Optional[str] = None
    tags: list[str] = []

    @property
    def correct_choice(self) -> Optional[Choice]:
        for choice in self.choices:
            if choice.is_correct:
                return choice
        return None


class Exam(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    code: str
    name: str
    description: str = ""
    time_limit: int = 45
    topic_id: Optional[UUID] = None
    questions: list[Question] = []


class ExamConfig(BaseModel):
    exam_code: Optional[str] = None
    exam_name: Optional[str] = None
    exam_description: str = ""
    time_limit: int = 45
    enable_images: bool = True
    custom_instructions: str = ""


class ThinkingSkillsConfig(ExamConfig):
    abstract_count: int = 10
    verbal_count: int = 8
    numerical_count: int = 8
    logical_count: int = 9


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
