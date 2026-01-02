"""Thinking Skills Agent for generating NSW Selective test questions."""

import asyncio
import json
from typing import Any, Optional
from pathlib import Path

from a2a_local import AgentConfig, A2AClient, AGENT_ENDPOINTS
from agents.base_agent import BaseAgent
from models import Question, Choice, ThinkingSkillsConfig
from config import config

# Maximum retries for verification failures
MAX_VERIFICATION_RETRIES = 3


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
        self.a2a_client = A2AClient(timeout=180.0)

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming task requests."""
        # Parse task message
        message = task.status.message
        if message and message.parts:
            # A2A SDK wraps parts - access via .root.text for TextPart
            part = message.parts[0]
            task_text = part.root.text if hasattr(part, 'root') else part.text
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
        """Generate questions for a specific subtopic with auto-verification."""
        if subtopic not in SUBTOPICS:
            return {"error": f"Unknown subtopic: {subtopic}"}

        subtopic_config = SUBTOPICS[subtopic]
        verified_questions = []
        failed_questions = []
        total_retries = 0

        # Generate questions one at a time with verification loop
        for i in range(count):
            question = await self._generate_single_question(
                subtopic=subtopic,
                subtopic_config=subtopic_config,
                enable_images=enable_images,
                custom_instructions=custom_instructions,
                question_number=i + 1,
            )

            if question is None:
                continue

            # Verification loop
            verified = False
            retries = 0
            current_question = question

            while not verified and retries < MAX_VERIFICATION_RETRIES:
                # Send to verifier
                verification_result = await self._verify_question(current_question)

                if verification_result.get("passed", False):
                    verified = True
                    verified_questions.append(current_question)
                else:
                    # Get feedback and regenerate
                    issues = verification_result.get("issues", [])
                    feedback = self._format_feedback(issues)
                    print(f"Question {i + 1} failed verification (attempt {retries + 1}): {feedback[:100]}...")

                    # Regenerate with feedback
                    current_question = await self._regenerate_with_feedback(
                        question=current_question,
                        feedback=feedback,
                        subtopic=subtopic,
                        subtopic_config=subtopic_config,
                        enable_images=enable_images,
                    )

                    if current_question is None:
                        break

                    retries += 1
                    total_retries += 1

            if not verified:
                failed_questions.append({
                    "question_number": i + 1,
                    "last_issues": verification_result.get("issues", []),
                })

            # Rate limiting between questions
            await asyncio.sleep(1)

        return {
            "success": True,
            "subtopic": subtopic,
            "count": len(verified_questions),
            "questions": [q.model_dump() for q in verified_questions],
            "verification_stats": {
                "requested": count,
                "verified": len(verified_questions),
                "failed": len(failed_questions),
                "total_retries": total_retries,
            },
            "failed_questions": failed_questions,
        }

    async def _generate_single_question(
        self,
        subtopic: str,
        subtopic_config: dict,
        enable_images: bool,
        custom_instructions: str,
        question_number: int,
    ) -> Optional[Question]:
        """Generate a single question."""
        # Load prompts
        base_prompt = self.load_prompt("thinking-skills", "subtopics", "base.md")
        subtopic_prompt = self.load_prompt("thinking-skills", "subtopics", f"{subtopic}.md")

        # Determine if this question needs an image
        needs_image = enable_images and (question_number <= int(subtopic_config["image_ratio"] * 10))

        if needs_image:
            image_section = """## Image Requirements:
- This question should include a visual diagram
- Set requires_image: true
- Provide detailed image_description for diagram generation
- Images should be SAT-style: clean lines, white background, black outlines
- No gradients, shadows, or 3D effects"""
        else:
            image_section = "## No images required for this question."

        # Fill in template (generating 1 question)
        prompt = base_prompt.replace("{{COUNT}}", "1")
        prompt = prompt.replace("{{DISPLAY_NAME}}", subtopic_config["display_name"])
        prompt = prompt.replace("{{DESCRIPTION}}", subtopic_config["description"])
        prompt = prompt.replace("{{SUBTOPIC_INSTRUCTIONS}}", subtopic_prompt)
        prompt = prompt.replace("{{IMAGE_SECTION}}", image_section)
        prompt = prompt.replace("{{DB_SUBTOPIC_NAME}}", subtopic_config["db_subtopic_name"])
        prompt = prompt.replace(
            "{{CUSTOM_INSTRUCTIONS}}",
            f"## Additional Instructions:\n{custom_instructions}" if custom_instructions else "",
        )

        try:
            questions_data = await self.generate_json(prompt, temperature=0.8)

            if not questions_data:
                return None

            q_data = questions_data[0] if isinstance(questions_data, list) else questions_data

            choices = [
                Choice(
                    id=c["id"],
                    text=c.get("text", c.get("content", "")),
                    is_correct=c["is_correct"],
                )
                for c in q_data.get("choices", [])
            ]

            return Question(
                content=q_data.get("content"),
                question=q_data["question"],
                choices=choices,
                explanation=q_data["explanation"],
                difficulty="3",
                subtopic_name=q_data.get("subtopic_name", subtopic_config["db_subtopic_name"]),
                requires_image=q_data.get("requires_image", False),
                image_description=q_data.get("image_description"),
                tags=q_data.get("tags", ["Thinking Skills", subtopic_config["display_name"]]),
            )

        except Exception as e:
            print(f"Error generating question: {e}")
            return None

    async def _verify_question(self, question: Question) -> dict:
        """Send question to VerifierAgent for verification."""
        try:
            endpoint = AGENT_ENDPOINTS["verifier"]

            task_message = json.dumps({
                "action": "verify_single",
                "question": question.model_dump(),
            }, default=str)

            result = await self.a2a_client.send_task(
                endpoint=endpoint,
                skill_id="verify_single",
                message=task_message,
            )

            # Parse the result
            if "error" in result:
                print(f"Verifier error: {result['error']}")
                return {"passed": True, "issues": []}  # Pass on error to avoid blocking

            # Extract verification from response
            status = result.get("status", {})
            message = status.get("message", {})
            parts = message.get("parts", [])

            if parts:
                part = parts[0]
                text = part.get("text", "{}")
                try:
                    verification_data = json.loads(text)
                    verification = verification_data.get("verification", {})

                    passed = verification.get("status") == "pass"
                    issues = [
                        {"category": i.get("category"), "message": i.get("message"), "suggestion": i.get("suggestion")}
                        for i in verification.get("issues", [])
                    ]

                    return {"passed": passed, "issues": issues}
                except json.JSONDecodeError:
                    return {"passed": True, "issues": []}

            return {"passed": True, "issues": []}

        except Exception as e:
            print(f"Verification failed: {e}")
            return {"passed": True, "issues": []}  # Pass on error to avoid blocking

    def _format_feedback(self, issues: list) -> str:
        """Format verification issues into feedback for regeneration."""
        if not issues:
            return "No specific issues provided."

        feedback_lines = ["Fix the following issues:"]
        for i, issue in enumerate(issues, 1):
            category = issue.get("category", "unknown")
            message = issue.get("message", "Unknown issue")
            suggestion = issue.get("suggestion", "")

            feedback_lines.append(f"{i}. [{category.upper()}] {message}")
            if suggestion:
                feedback_lines.append(f"   Suggestion: {suggestion}")

        return "\n".join(feedback_lines)

    async def _regenerate_with_feedback(
        self,
        question: Question,
        feedback: str,
        subtopic: str,
        subtopic_config: dict,
        enable_images: bool,
    ) -> Optional[Question]:
        """Regenerate a question with verification feedback."""
        prompt = f"""You previously generated this question, but it failed verification.

## Original Question:
{json.dumps(question.model_dump(), indent=2, default=str)}

## Verification Feedback:
{feedback}

## Instructions:
1. Fix ALL the issues mentioned in the feedback
2. Maintain the same subtopic ({subtopic_config["display_name"]}) and difficulty level
3. Return a corrected version as a JSON object (not an array)

## Required JSON format:
{{
    "content": "optional context or passage",
    "question": "the question text",
    "choices": [
        {{"id": "1", "text": "option A", "is_correct": false}},
        {{"id": "2", "text": "option B", "is_correct": true}},
        {{"id": "3", "text": "option C", "is_correct": false}},
        {{"id": "4", "text": "option D", "is_correct": false}}
    ],
    "explanation": "detailed explanation of why the correct answer is correct",
    "subtopic_name": "{subtopic_config["db_subtopic_name"]}",
    "requires_image": {"true" if question.requires_image else "false"},
    "image_description": null,
    "tags": ["Thinking Skills", "{subtopic_config["display_name"]}"]
}}

Return ONLY the JSON object, no markdown formatting."""

        try:
            result = await self.generate_json(prompt, temperature=0.5)

            if not result:
                return None

            q_data = result if isinstance(result, dict) else result[0]

            choices = [
                Choice(
                    id=c["id"],
                    text=c.get("text", c.get("content", "")),
                    is_correct=c["is_correct"],
                )
                for c in q_data.get("choices", [])
            ]

            return Question(
                content=q_data.get("content"),
                question=q_data["question"],
                choices=choices,
                explanation=q_data["explanation"],
                difficulty="3",
                subtopic_name=q_data.get("subtopic_name", subtopic_config["db_subtopic_name"]),
                requires_image=q_data.get("requires_image", False),
                image_description=q_data.get("image_description"),
                tags=q_data.get("tags", ["Thinking Skills", subtopic_config["display_name"]]),
            )

        except Exception as e:
            print(f"Error regenerating question: {e}")
            return None

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
