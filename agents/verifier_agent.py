"""Verifier Agent for validating generated exam questions."""

import asyncio
import json
from typing import Any

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from models.verification import (
    VerificationStatus,
    VerificationIssue,
    QuestionVerification,
    BatchVerificationResult,
)
from config import config


class VerifierAgent(BaseAgent):
    """Agent for verifying exam question correctness and quality.

    Uses a simple PASS/FAIL approach - any issue means the question fails
    and needs to be regenerated with feedback.
    """

    BATCH_SIZE = 5  # Questions per verification batch

    def __init__(self):
        agent_config = AgentConfig(
            name="VerifierAgent",
            description="Verifies exam question correctness, quality, and formatting",
            port=config.ports.verifier,
            skills=[
                {
                    "id": "verify_questions",
                    "name": "Verify Questions",
                    "description": "Verify a batch of questions for correctness and quality",
                    "tags": ["verification", "quality"],
                },
                {
                    "id": "verify_single",
                    "name": "Verify Single Question",
                    "description": "Verify a single question in detail",
                    "tags": ["verification"],
                },
            ],
        )
        super().__init__(agent_config)

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming verification tasks."""
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

        action = task_data.get("action", "verify_questions")

        if action == "verify_questions":
            return await self.verify_questions(
                questions=task_data.get("questions", []),
            )
        elif action == "verify_single":
            return await self.verify_single(
                question=task_data.get("question", {}),
            )
        else:
            return {"error": f"Unknown action: {action}"}

    async def verify_questions(self, questions: list[dict]) -> dict:
        """Verify a batch of questions. Returns pass/fail for each."""
        if not questions:
            return {
                "success": True,
                "verification": BatchVerificationResult(
                    total_questions=0,
                    passed=0,
                    failed=0,
                    questions=[],
                ).model_dump(),
            }

        all_verifications = []

        # Process in batches
        for i in range(0, len(questions), self.BATCH_SIZE):
            batch = questions[i:i + self.BATCH_SIZE]
            batch_results = await self._verify_batch(batch)
            all_verifications.extend(batch_results)

            # Rate limiting between batches
            if i + self.BATCH_SIZE < len(questions):
                await asyncio.sleep(1)

        # Calculate summary statistics
        passed = sum(1 for v in all_verifications if v.status == VerificationStatus.PASS)
        failed = sum(1 for v in all_verifications if v.status == VerificationStatus.FAIL)

        result = BatchVerificationResult(
            total_questions=len(questions),
            passed=passed,
            failed=failed,
            questions=all_verifications,
        )

        return {
            "success": True,
            "verification": result.model_dump(),
            "summary": {
                "total": result.total_questions,
                "passed": result.passed,
                "failed": result.failed,
                "pass_rate": result.pass_rate,
                "all_passed": result.all_passed,
            },
        }

    async def _verify_batch(self, questions: list[dict]) -> list[QuestionVerification]:
        """Run all verification checks on a batch of questions."""
        questions_json = json.dumps(questions, indent=2, default=str)

        # Run all 4 verifications in parallel
        answer_task = self._verify_answers(questions_json)
        quality_task = self._verify_quality(questions_json)
        format_task = self._verify_format(questions_json)
        explanation_task = self._verify_explanations(questions_json)

        results = await asyncio.gather(
            answer_task, quality_task, format_task, explanation_task,
            return_exceptions=True
        )

        answer_results = results[0] if not isinstance(results[0], Exception) else []
        quality_results = results[1] if not isinstance(results[1], Exception) else []
        format_results = results[2] if not isinstance(results[2], Exception) else []
        explanation_results = results[3] if not isinstance(results[3], Exception) else []

        # Combine results for each question
        verifications = []
        for i, q in enumerate(questions):
            verification = self._combine_results(
                question=q,
                index=i,
                answer_result=answer_results[i] if i < len(answer_results) else {},
                quality_result=quality_results[i] if i < len(quality_results) else {},
                format_result=format_results[i] if i < len(format_results) else {},
                explanation_result=explanation_results[i] if i < len(explanation_results) else {},
            )
            verifications.append(verification)

        return verifications

    async def _verify_answers(self, questions_json: str) -> list[dict]:
        """Independently solve and verify answers."""
        prompt = self.load_prompt("verification", "verify_answer.md")
        prompt = prompt.replace("{{QUESTIONS_JSON}}", questions_json)

        try:
            result = await self.generate_json(prompt, temperature=0.3)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Answer verification error: {e}")
            return []

    async def _verify_quality(self, questions_json: str) -> list[dict]:
        """Check question quality."""
        prompt = self.load_prompt("verification", "verify_quality.md")
        prompt = prompt.replace("{{QUESTIONS_JSON}}", questions_json)

        try:
            result = await self.generate_json(prompt, temperature=0.5)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Quality verification error: {e}")
            return []

    async def _verify_format(self, questions_json: str) -> list[dict]:
        """Validate formatting and structure."""
        prompt = self.load_prompt("verification", "verify_format.md")
        prompt = prompt.replace("{{QUESTIONS_JSON}}", questions_json)

        try:
            result = await self.generate_json(prompt, temperature=0.2)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Format verification error: {e}")
            return []

    async def _verify_explanations(self, questions_json: str) -> list[dict]:
        """Verify explanation-answer alignment."""
        prompt = self.load_prompt("verification", "verify_explanation.md")
        prompt = prompt.replace("{{QUESTIONS_JSON}}", questions_json)

        try:
            result = await self.generate_json(prompt, temperature=0.4)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Explanation verification error: {e}")
            return []

    def _combine_results(
        self,
        question: dict,
        index: int,
        answer_result: dict,
        quality_result: dict,
        format_result: dict,
        explanation_result: dict,
    ) -> QuestionVerification:
        """Combine all verification results. ANY failure = FAIL status."""
        issues = []

        # Answer verification
        answer_correct = answer_result.get("answer_matches", True)
        answer_confidence = answer_result.get("confidence", 0.5)
        verified_choice = answer_result.get("my_answer_choice_id")

        if not answer_correct:
            issue_msg = answer_result.get("issue") or f"Answer verification failed. Verifier determined correct answer is choice {verified_choice}"
            issues.append(VerificationIssue(
                category="answer",
                message=issue_msg,
                suggestion=answer_result.get("my_solution"),
            ))

        # Quality checks
        quality_ok = quality_result.get("all_passed", True)
        for issue_text in quality_result.get("issues", []):
            issues.append(VerificationIssue(
                category="quality",
                message=issue_text,
            ))

        # Format checks
        format_ok = format_result.get("all_passed", True)
        for issue_text in format_result.get("issues", []):
            issues.append(VerificationIssue(
                category="format",
                message=issue_text,
            ))

        # Explanation checks
        explanation_ok = explanation_result.get("all_passed", True)
        for issue_text in explanation_result.get("issues", []):
            issues.append(VerificationIssue(
                category="explanation",
                message=issue_text,
            ))

        # PASS only if ALL checks pass
        all_passed = answer_correct and quality_ok and format_ok and explanation_ok
        status = VerificationStatus.PASS if all_passed else VerificationStatus.FAIL

        return QuestionVerification(
            question_id=str(question.get("id", "")),
            question_text=question.get("question", "")[:100],
            status=status,
            answer_correct=answer_correct,
            answer_confidence=answer_confidence,
            verified_correct_choice=verified_choice,
            quality_ok=quality_ok,
            format_ok=format_ok,
            explanation_ok=explanation_ok,
            issues=issues,
        )

    async def verify_single(self, question: dict) -> dict:
        """Verify a single question with detailed analysis."""
        result = await self.verify_questions([question])
        if result.get("success") and result.get("verification", {}).get("questions"):
            return {
                "success": True,
                "verification": result["verification"]["questions"][0],
            }
        return result


async def main():
    """Run the Verifier Agent."""
    agent = VerifierAgent()
    print(f"Starting Verifier Agent on port {config.ports.verifier}...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
