"""Correctness Agent - verifies answer correctness by working backwards and forwards."""

import json
from typing import Any

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from config import config


class CorrectnessAgent(BaseAgent):
    """Agent that verifies answer correctness by independent solving."""

    def __init__(self):
        agent_config = AgentConfig(
            name="CorrectnessAgent",
            description="Verifies answer correctness by working backwards and forwards",
            port=config.ports.correctness,
            skills=[
                {
                    "id": "verify_correctness",
                    "name": "Verify Correctness",
                    "description": "Work backwards from answer and solve forwards to verify correctness",
                    "tags": ["correctness", "verification", "math"],
                },
            ],
        )
        super().__init__(agent_config)

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming task requests."""
        message = task.status.message
        if message and message.parts:
            part = message.parts[0]
            task_text = part.root.text if hasattr(part, "root") else part.text
            try:
                task_data = json.loads(task_text)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON in task message"}
        else:
            return {"error": "No task data provided"}

        action = task_data.get("action", "")

        if action == "verify_correctness":
            return await self.verify_correctness(
                question=task_data.get("question", {}),
                blueprint=task_data.get("blueprint", {}),
            )
        else:
            return {"error": f"Unknown action: {action}"}

    async def verify_correctness(self, question: dict, blueprint: dict) -> dict:
        """
        Verify the question by:
        1. Working backwards from the marked answer
        2. Solving forwards independently
        3. Checking answer properties match requirements
        """
        try:
            prompt = self._build_verification_prompt(question, blueprint)

            result_data = await self.generate_json(prompt, temperature=0.1)

            if not result_data:
                return {"success": False, "error": "Failed to verify correctness"}

            # Extract verification results
            backwards = result_data.get("backwards_verification", {})
            forwards = result_data.get("independent_solution", {})

            answer_correct = result_data.get("answer_is_correct", False)
            issues = result_data.get("issues", [])
            suggestions = result_data.get("suggestions", [])

            return {
                "success": True,
                "verified": answer_correct,
                "backwards_check": backwards,
                "forwards_solution": forwards,
                "answer_matches": backwards.get("consistent", False) and answer_correct,
                "issues": issues,
                "suggestions": suggestions,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _build_verification_prompt(self, question: dict, blueprint: dict) -> str:
        """Build the prompt for verification."""
        content = question.get("content", "")
        question_text = question.get("question", "")
        choices_text = self._format_choices(question)
        correct_answer = self._get_correct_answer(question)

        concept_name = blueprint.get("concept_name", "Unknown")
        subtopic_name = blueprint.get("subtopic_name", "Unknown")

        return f"""You are a verification expert. Your job is to verify this question has the correct answer.

## Context/Setup
{content}

## Question
{question_text}

## Answer Choices
{choices_text}

## Marked Correct Answer
{correct_answer}

## Concept: {concept_name} ({subtopic_name})

---

## YOUR TASK

### STEP 1: Work BACKWARDS from the Answer
Given that the marked answer is "{correct_answer}", work backwards:
- What setup/values/conditions would produce this answer?
- Does the question actually provide those values?
- Are there any inconsistencies between the question and the answer?

### STEP 2: Solve FORWARDS Independently
Now IGNORE the marked answer. Solve the problem from scratch:
- Extract all relevant values from the question
- Show your complete working step by step
- What answer do you arrive at?

### STEP 3: Compare and Verify
- Does your independent answer match the marked answer?
- Are there any mathematical/logical errors?
- Is the answer reasonable and valid for this type of question?

## OUTPUT JSON:
{{
  "backwards_verification": {{
    "what_answer_requires": "Describe what values/setup would produce this answer",
    "what_question_provides": "Describe what the question actually gives us",
    "consistent": true or false,
    "discrepancies": ["List any mismatches or issues"]
  }},
  "independent_solution": {{
    "extracted_values": {{"key": "value pairs of data from question"}},
    "working": ["step 1: ...", "step 2: ...", "step 3: ..."],
    "my_answer": "Your calculated answer"
  }},
  "answers_match": true or false,
  "answer_is_correct": true or false,
  "issues": ["List any problems found - empty array if none"],
  "suggestions": ["How to fix each issue - empty array if none"]
}}"""

    def _format_choices(self, question: dict) -> str:
        """Format choices for display in prompt."""
        choices = question.get("choices", [])
        if not choices:
            return "No choices provided"

        lines = []
        for i, choice in enumerate(choices):
            letter = chr(65 + i)  # A, B, C, D, E
            text = choice.get("text", "")
            is_correct = choice.get("is_correct", False)
            marker = " [MARKED CORRECT]" if is_correct else ""
            lines.append(f"{letter}. {text}{marker}")

        return "\n".join(lines)

    def _get_correct_answer(self, question: dict) -> str:
        """Get the correct answer text."""
        choices = question.get("choices", [])
        for i, choice in enumerate(choices):
            if choice.get("is_correct", False):
                letter = chr(65 + i)
                return f"{letter}. {choice.get('text', '')}"
        return "Unknown"
