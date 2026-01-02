"""Thinking Skills Agent for generating NSW Selective test questions."""

import asyncio
import json
from typing import Any, Optional
from pathlib import Path

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from models import Question, Choice, ThinkingSkillsConfig
from config import config


# Subtopic configurations
SUBTOPICS = {
    "analogies": {
        "display_name": "Analogies",
        "description": "Word analogies, relationships, and logical connections between concepts",
        "db_subtopic_name": "Analogies",
        "image_ratio": 0.05,
    },
    "critical_thinking": {
        "display_name": "Critical Thinking",
        "description": "Analyzing arguments, evaluating evidence, and drawing logical conclusions",
        "db_subtopic_name": "Critical Thinking",
        "image_ratio": 0.05,
    },
    "deduction": {
        "display_name": "Deduction",
        "description": "Syllogisms, logical deduction, and drawing conclusions from premises",
        "db_subtopic_name": "Deduction",
        "image_ratio": 0.20,
    },
    "inference": {
        "display_name": "Inference",
        "description": "Drawing conclusions from given information and implicit relationships",
        "db_subtopic_name": "Inference",
        "image_ratio": 0.10,
    },
    "logical_reasoning": {
        "display_name": "Logical Reasoning",
        "description": "Venn diagrams, seating arrangements, and complex logical problems",
        "db_subtopic_name": "Logical Reasoning",
        "image_ratio": 0.40,
    },
    "pattern_recognition": {
        "display_name": "Pattern Recognition",
        "description": "Visual patterns, sequences, and code-breaking puzzles",
        "db_subtopic_name": "Pattern Recognition",
        "image_ratio": 0.30,
    },
    "sequencing": {
        "display_name": "Sequencing",
        "description": "Number sequences, letter patterns, and ordered arrangements",
        "db_subtopic_name": "Sequencing",
        "image_ratio": 0.15,
    },
    "spatial_reasoning": {
        "display_name": "Spatial Reasoning",
        "description": "3D visualization, rotations, reflections, and spatial transformations",
        "db_subtopic_name": "Spatial Reasoning",
        "image_ratio": 0.50,
    },
}

# Map config field names to subtopic keys
CONFIG_FIELD_MAP = {
    "analogies_count": "analogies",
    "critical_thinking_count": "critical_thinking",
    "deduction_count": "deduction",
    "inference_count": "inference",
    "logical_count": "logical_reasoning",
    "pattern_recognition_count": "pattern_recognition",
    "sequencing_count": "sequencing",
    "spatial_reasoning_count": "spatial_reasoning",
}


class ThinkingSkillsAgent(BaseAgent):
    """Agent for generating Thinking Skills questions."""

    def __init__(self):
        agent_config = AgentConfig(
            name="ThinkingSkillsAgent",
            description="Generates NSW Selective Schools Thinking Skills exam questions",
            port=config.ports.thinking_skills,
            skills=[
                {
                    "id": "generate_questions",
                    "name": "Generate Questions",
                    "description": "Generate thinking skills questions for a specific subtopic",
                    "tags": ["generation", "thinking-skills"],
                },
                {
                    "id": "generate_exam",
                    "name": "Generate Full Exam",
                    "description": "Generate a complete thinking skills exam with all subtopics",
                    "tags": ["generation", "exam"],
                },
            ],
        )
        super().__init__(agent_config)

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming task requests."""
        # Parse task message
        message = task.status.message
        if message and message.parts:
            task_text = message.parts[0].text
            try:
                task_data = json.loads(task_text)
            except json.JSONDecodeError:
                task_data = {"action": "generate_exam"}
        else:
            task_data = {"action": "generate_exam"}

        action = task_data.get("action", "generate_exam")

        if action == "generate_questions":
            return await self.generate_questions(
                subtopic=task_data.get("subtopic", "pattern_recognition"),
                count=task_data.get("count", 5),
                enable_images=task_data.get("enable_images", True),
                custom_instructions=task_data.get("custom_instructions", ""),
            )
        elif action == "generate_exam":
            exam_config = ThinkingSkillsConfig(**task_data.get("config", {}))
            return await self.generate_full_exam(exam_config)
        else:
            return {"error": f"Unknown action: {action}"}

    async def generate_questions(
        self,
        subtopic: str,
        count: int,
        enable_images: bool = True,
        custom_instructions: str = "",
    ) -> dict:
        """Generate questions for a specific subtopic."""
        if subtopic not in SUBTOPICS:
            return {"error": f"Unknown subtopic: {subtopic}"}

        subtopic_config = SUBTOPICS[subtopic]

        # Load prompts
        base_prompt = self.load_prompt("thinking-skills", "subtopics", "base.md")
        subtopic_prompt = self.load_prompt("thinking-skills", "subtopics", f"{subtopic}.md")

        # Calculate image count
        image_count = 0
        if enable_images:
            image_count = max(1, int(count * subtopic_config["image_ratio"]))

        # Build image section
        if image_count > 0:
            image_section = f"""## Image Requirements:
- {image_count} of these {count} questions should include visual diagrams
- For those questions, set requires_image: true
- Provide detailed image_description for diagram generation
- Images should be SAT-style: clean lines, white background, black outlines
- No gradients, shadows, or 3D effects"""
        else:
            image_section = "## No images required for this batch."

        # Fill in template
        prompt = base_prompt.replace("{{COUNT}}", str(count))
        prompt = prompt.replace("{{DISPLAY_NAME}}", subtopic_config["display_name"])
        prompt = prompt.replace("{{DESCRIPTION}}", subtopic_config["description"])
        prompt = prompt.replace("{{SUBTOPIC_INSTRUCTIONS}}", subtopic_prompt)
        prompt = prompt.replace("{{IMAGE_SECTION}}", image_section)
        prompt = prompt.replace("{{DB_SUBTOPIC_NAME}}", subtopic_config["db_subtopic_name"])
        prompt = prompt.replace(
            "{{CUSTOM_INSTRUCTIONS}}",
            f"## Additional Instructions:\n{custom_instructions}" if custom_instructions else "",
        )

        # Generate questions
        try:
            questions_data = await self.generate_json(prompt, temperature=0.8)

            # Validate and convert to Question objects
            questions = []
            for q_data in questions_data:
                choices = [
                    Choice(
                        id=c["id"],
                        text=c.get("text", c.get("content", "")),
                        is_correct=c["is_correct"],
                    )
                    for c in q_data.get("choices", [])
                ]

                question = Question(
                    content=q_data.get("content"),
                    question=q_data["question"],
                    choices=choices,
                    explanation=q_data["explanation"],
                    difficulty=str(q_data.get("difficulty", "2")),
                    subtopic_name=q_data.get("subtopic_name", subtopic_config["db_subtopic_name"]),
                    requires_image=q_data.get("requires_image", False),
                    image_description=q_data.get("image_description"),
                    tags=q_data.get("tags", ["Thinking Skills", subtopic_config["display_name"]]),
                )
                questions.append(question)

            return {
                "success": True,
                "subtopic": subtopic,
                "count": len(questions),
                "questions": [q.model_dump() for q in questions],
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "subtopic": subtopic,
            }

    async def generate_full_exam(self, exam_config: ThinkingSkillsConfig) -> dict:
        """Generate a complete thinking skills exam."""
        all_questions = []
        results = []

        # Generate questions for each subtopic
        for config_field, subtopic_key in CONFIG_FIELD_MAP.items():
            count = getattr(exam_config, config_field, 0)
            if count > 0:
                result = await self.generate_questions(
                    subtopic=subtopic_key,
                    count=count,
                    enable_images=exam_config.enable_images,
                    custom_instructions=exam_config.custom_instructions,
                )
                results.append(result)

                if result.get("success"):
                    all_questions.extend(result.get("questions", []))

                # Rate limiting - wait between API calls
                await asyncio.sleep(2)

        return {
            "success": True,
            "total_questions": len(all_questions),
            "questions": all_questions,
            "subtopic_results": results,
            "exam_config": exam_config.model_dump(),
        }


async def main():
    """Run the Thinking Skills Agent."""
    agent = ThinkingSkillsAgent()
    print(f"Starting Thinking Skills Agent on port {config.ports.thinking_skills}...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
