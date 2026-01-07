"""Curriculum and concept models for the multi-agent pipeline."""

from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BloomLevel(str, Enum):
    """Bloom's taxonomy levels for cognitive skills."""
    RECALL = "recall"
    COMPREHENSION = "comprehension"
    APPLICATION = "application"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    EVALUATION = "evaluation"


class AtomicConcept(BaseModel):
    """An atomic, testable concept within a subtopic."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str

    # Difficulty range this concept can be tested at (1-3)
    difficulty_min: int = 1
    difficulty_max: int = 3

    # Cognitive skills this concept tests
    bloom_levels: list[BloomLevel] = [BloomLevel.APPLICATION]

    # Common student misconceptions for this concept
    common_misconceptions: list[str] = []

    # Question patterns that work well for this concept
    question_patterns: list[str] = []

    # Example question stems
    example_stems: list[str] = []

    # Whether this concept typically requires an image
    typically_requires_image: bool = False

    # Image types that work for this concept (if applicable)
    image_types: list[str] = []


class PrerequisiteEdge(BaseModel):
    """Represents a prerequisite relationship between concepts."""
    prerequisite_id: str  # Concept that must be understood first
    dependent_id: str  # Concept that depends on the prerequisite


class ConceptGraph(BaseModel):
    """A graph of concepts with prerequisite relationships."""
    subtopic_id: UUID
    subtopic_name: str
    topic_id: UUID
    topic_name: str
    concepts: list[AtomicConcept]
    prerequisites: list[PrerequisiteEdge] = []

    def get_concept(self, concept_id: str) -> Optional[AtomicConcept]:
        """Get a concept by ID."""
        for concept in self.concepts:
            if concept.id == concept_id:
                return concept
        return None

    def get_concepts_for_difficulty(self, difficulty: int) -> list[AtomicConcept]:
        """Get concepts that can be tested at a given difficulty level."""
        return [
            c for c in self.concepts
            if c.difficulty_min <= difficulty <= c.difficulty_max
        ]


class ConceptSelection(BaseModel):
    """Result of selecting a concept for question generation."""
    concept: AtomicConcept
    target_difficulty: int  # 1, 2, or 3
    target_bloom_level: BloomLevel
    selected_misconceptions: list[str] = []  # For distractor generation
    selected_pattern: Optional[str] = None  # Question pattern to use
