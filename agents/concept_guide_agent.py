"""Concept Guide Agent for serving atomic concepts from the custom guide."""

import asyncio
import json
import random
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from models import (
    AtomicConcept,
    ConceptGraph,
    ConceptSelection,
    BloomLevel,
)
from config import config


class ConceptGuideAgent(BaseAgent):
    """Agent that provides atomic concepts from our custom concept guide."""

    def __init__(self):
        agent_config = AgentConfig(
            name="ConceptGuideAgent",
            description="Provides atomic concepts for question generation from custom guide",
            port=config.ports.concept_guide,
            skills=[
                {
                    "id": "get_concepts",
                    "name": "Get Concepts",
                    "description": "Get all concepts for a subtopic",
                    "tags": ["concepts", "curriculum"],
                },
                {
                    "id": "select_concept",
                    "name": "Select Concept",
                    "description": "Select a concept appropriate for the target difficulty",
                    "tags": ["concepts", "selection"],
                },
                {
                    "id": "list_subtopics",
                    "name": "List Subtopics",
                    "description": "List available subtopics with concept counts",
                    "tags": ["concepts", "info"],
                },
            ],
        )
        super().__init__(agent_config)
        self._concept_graphs: dict[str, ConceptGraph] = {}
        self._loaded = False

    async def _ensure_loaded(self):
        """Load concept files if not already loaded."""
        if self._loaded:
            return

        concepts_dir = config.data_dir / "concepts" / "thinking_skills"

        if not concepts_dir.exists():
            print(f"Warning: Concepts directory not found: {concepts_dir}")
            self._loaded = True
            return

        for json_file in concepts_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)

                subtopic_key = json_file.stem  # e.g., "analogies"

                # Parse concepts
                concepts = []
                for c_data in data.get("concepts", []):
                    concept = AtomicConcept(
                        id=c_data["id"],
                        name=c_data["name"],
                        description=c_data["description"],
                        subtopic_id=UUID(data["subtopic_id"]),
                        subtopic_name=data["subtopic_name"],
                        topic_id=UUID(data["topic_id"]),
                        topic_name=data["topic_name"],
                        difficulty_min=c_data.get("difficulty_min", 1),
                        difficulty_max=c_data.get("difficulty_max", 3),
                        bloom_levels=[BloomLevel(b) for b in c_data.get("bloom_levels", ["application"])],
                        common_misconceptions=c_data.get("common_misconceptions", []),
                        question_patterns=c_data.get("question_patterns", []),
                        example_stems=c_data.get("example_stems", []),
                        typically_requires_image=data.get("typically_requires_image", False),
                        image_types=data.get("image_types", []),
                    )
                    concepts.append(concept)

                # Create concept graph
                graph = ConceptGraph(
                    subtopic_id=UUID(data["subtopic_id"]),
                    subtopic_name=data["subtopic_name"],
                    topic_id=UUID(data["topic_id"]),
                    topic_name=data["topic_name"],
                    concepts=concepts,
                )

                self._concept_graphs[subtopic_key] = graph
                print(f"Loaded {len(concepts)} concepts for {subtopic_key}")

            except Exception as e:
                print(f"Error loading {json_file}: {e}")

        self._loaded = True

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming task requests."""
        await self._ensure_loaded()

        message = task.status.message
        if message and message.parts:
            part = message.parts[0]
            task_text = part.root.text if hasattr(part, 'root') else part.text
            try:
                task_data = json.loads(task_text)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON in task message"}
        else:
            return {"error": "No task data provided"}

        action = task_data.get("action", "")

        if action == "get_concepts":
            return await self.get_concepts(task_data.get("subtopic"))
        elif action == "select_concept":
            return await self.select_concept(
                subtopic=task_data.get("subtopic"),
                difficulty=task_data.get("difficulty", 3),
                exclude_ids=task_data.get("exclude_ids", []),
            )
        elif action == "list_subtopics":
            return await self.list_subtopics()
        else:
            return {"error": f"Unknown action: {action}"}

    async def get_concepts(self, subtopic: Optional[str] = None) -> dict:
        """Get all concepts, optionally filtered by subtopic."""
        if subtopic:
            if subtopic not in self._concept_graphs:
                return {
                    "success": False,
                    "error": f"Unknown subtopic: {subtopic}",
                    "available": list(self._concept_graphs.keys()),
                }

            graph = self._concept_graphs[subtopic]
            return {
                "success": True,
                "subtopic": subtopic,
                "subtopic_id": str(graph.subtopic_id),
                "subtopic_name": graph.subtopic_name,
                "concept_count": len(graph.concepts),
                "concepts": [c.model_dump(mode="json") for c in graph.concepts],
            }
        else:
            # Return all concepts
            all_concepts = []
            for key, graph in self._concept_graphs.items():
                for concept in graph.concepts:
                    all_concepts.append({
                        "subtopic_key": key,
                        **concept.model_dump(mode="json"),
                    })

            return {
                "success": True,
                "total_concepts": len(all_concepts),
                "concepts": all_concepts,
            }

    async def select_concept(
        self,
        subtopic: str,
        difficulty: int = 3,
        exclude_ids: list[str] = None,
    ) -> dict:
        """Select a concept appropriate for the target difficulty."""
        exclude_ids = exclude_ids or []

        if subtopic not in self._concept_graphs:
            return {
                "success": False,
                "error": f"Unknown subtopic: {subtopic}",
                "available": list(self._concept_graphs.keys()),
            }

        graph = self._concept_graphs[subtopic]

        # Filter concepts by difficulty and exclusions
        eligible = [
            c for c in graph.concepts
            if c.difficulty_min <= difficulty <= c.difficulty_max
            and c.id not in exclude_ids
        ]

        if not eligible:
            # Fall back to any concept not excluded
            eligible = [c for c in graph.concepts if c.id not in exclude_ids]

        if not eligible:
            return {
                "success": False,
                "error": "No eligible concepts available",
            }

        # Select randomly from eligible concepts
        selected = random.choice(eligible)

        # Choose appropriate bloom level
        target_bloom = BloomLevel.APPLICATION
        if difficulty >= 3 and BloomLevel.ANALYSIS in selected.bloom_levels:
            target_bloom = BloomLevel.ANALYSIS
        elif difficulty <= 1 and BloomLevel.COMPREHENSION in selected.bloom_levels:
            target_bloom = BloomLevel.COMPREHENSION

        # Select misconceptions for distractors (up to 3)
        selected_misconceptions = selected.common_misconceptions[:3]

        # Select a question pattern if available
        selected_pattern = None
        if selected.question_patterns:
            selected_pattern = random.choice(selected.question_patterns)

        selection = ConceptSelection(
            concept=selected,
            target_difficulty=difficulty,
            target_bloom_level=target_bloom,
            selected_misconceptions=selected_misconceptions,
            selected_pattern=selected_pattern,
        )

        return {
            "success": True,
            "selection": selection.model_dump(mode="json"),
        }

    async def list_subtopics(self) -> dict:
        """List available subtopics with their concept counts."""
        subtopics = []

        for key, graph in self._concept_graphs.items():
            subtopics.append({
                "key": key,
                "subtopic_id": str(graph.subtopic_id),
                "subtopic_name": graph.subtopic_name,
                "topic_name": graph.topic_name,
                "concept_count": len(graph.concepts),
                "difficulty_range": {
                    "min": min(c.difficulty_min for c in graph.concepts) if graph.concepts else 1,
                    "max": max(c.difficulty_max for c in graph.concepts) if graph.concepts else 3,
                },
            })

        return {
            "success": True,
            "subtopics": subtopics,
            "total_subtopics": len(subtopics),
            "total_concepts": sum(s["concept_count"] for s in subtopics),
        }


async def main():
    """Run the Concept Guide Agent."""
    agent = ConceptGuideAgent()
    print(f"Starting Concept Guide Agent on port {config.ports.concept_guide}...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
