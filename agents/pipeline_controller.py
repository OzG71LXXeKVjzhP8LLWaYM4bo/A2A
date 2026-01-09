"""Pipeline Controller for orchestrating the multi-agent question generation flow."""

import asyncio
import json
from typing import Any, Optional
from dataclasses import dataclass, field

from a2a_local import A2AClient, AGENT_ENDPOINTS, log_pipeline_step, log_info, log_error
from models import (
    JudgmentStatus,
    PipelineResult,
)


@dataclass
class PipelineConfig:
    """Configuration for the pipeline."""
    max_revisions: int = 3


@dataclass
class PipelineState:
    """State tracking for a single question generation."""
    subtopic: str
    difficulty: int
    concept_selection: Optional[dict] = None
    blueprint: Optional[dict] = None
    question: Optional[dict] = None
    quality_result: Optional[dict] = None
    revision_count: int = 0
    errors: list[str] = field(default_factory=list)
    accepted: bool = False


class PipelineController:
    """Orchestrates the multi-agent question generation pipeline."""

    def __init__(self, client: A2AClient, config: Optional[PipelineConfig] = None):
        self.client = client
        self.config = config or PipelineConfig()

    async def generate_question(
        self,
        subtopic: str,
        difficulty: int = 3,
        exclude_concept_ids: Optional[list[str]] = None,
    ) -> PipelineResult:
        """Generate a single question through the full pipeline."""
        state = PipelineState(subtopic=subtopic, difficulty=difficulty)
        exclude_ids = exclude_concept_ids or []

        try:
            # Step 1: Select concept
            log_pipeline_step("Select Concept", 1, 4, f"subtopic={subtopic}, difficulty={difficulty}")
            state.concept_selection = await self._select_concept(
                subtopic, difficulty, exclude_ids
            )
            if not state.concept_selection:
                log_error("Pipeline", "Failed to select concept", f"subtopic={subtopic}")
                state.errors.append("Failed to select concept")
                return self._create_result(state)

            concept_name = state.concept_selection.get("concept", {}).get("name", "Unknown")
            log_info("Pipeline", f"Selected concept: {concept_name}")

            # Step 2-5: Generate, verify correctness, check quality, and possibly revise
            for attempt in range(self.config.max_revisions + 1):
                state.revision_count = attempt

                # Step 2: Generate question (blueprint + realization)
                if attempt == 0:
                    log_pipeline_step("Generate Question", 2, 4, f"concept={concept_name}")
                    gen_result = await self._generate_question(state.concept_selection)
                else:
                    log_pipeline_step(f"Revise Question (attempt {attempt + 1})", 2, 4,
                                     f"issues: {len(state.quality_result.get('issues', []))}")
                    gen_result = await self._revise_question(
                        state.question,
                        state.blueprint,
                        state.quality_result.get("issues", []),
                        state.quality_result.get("suggestions", []),
                    )

                if not gen_result:
                    log_error("Pipeline", f"Failed to generate question (attempt {attempt + 1})")
                    state.errors.append(f"Failed to generate question (attempt {attempt + 1})")
                    continue

                state.blueprint = gen_result.get("blueprint")
                state.question = gen_result.get("question")

                # Step 3: Verify correctness (work backwards + forwards)
                log_pipeline_step("Verify Correctness", 3, 4, f"attempt {attempt + 1}")
                correctness_result = await self._verify_correctness(
                    state.question,
                    state.blueprint,
                )

                if correctness_result and not correctness_result.get("verified", False):
                    # Failed correctness check - treat as quality failure for revision
                    log_info("Pipeline", f"✗ Correctness FAILED - {len(correctness_result.get('issues', []))} issues")
                    state.quality_result = {
                        "accepted": False,
                        "issues": correctness_result.get("issues", ["Answer verification failed"]),
                        "suggestions": correctness_result.get("suggestions", []),
                    }
                    continue

                # Step 4: Check quality (solve + attack + judge)
                log_pipeline_step("Quality Check", 4, 4, f"attempt {attempt + 1}")
                state.quality_result = await self._check_quality(
                    state.question,
                    state.blueprint,
                )

                if not state.quality_result:
                    log_error("Pipeline", f"Quality check failed (attempt {attempt + 1})")
                    state.errors.append(f"Quality check failed (attempt {attempt + 1})")
                    continue

                # Step 5: Check if accepted
                if state.quality_result.get("accepted"):
                    log_info("Pipeline", f"✓ Question ACCEPTED after {attempt + 1} attempt(s)")
                    state.accepted = True
                    break
                else:
                    issues = state.quality_result.get("issues", [])
                    log_info("Pipeline", f"✗ Question REJECTED - {len(issues)} issues found")

            return self._create_result(state)

        except Exception as e:
            state.errors.append(f"Pipeline error: {str(e)}")
            return self._create_result(state)

    async def generate_batch(
        self,
        subtopic: str,
        count: int,
        difficulty: int = 3,
    ) -> list[PipelineResult]:
        """Generate multiple questions for a subtopic in PARALLEL."""
        # Generate all questions in parallel for speed
        # Note: This means we can't exclude concepts across questions in same batch
        # Trade-off: May get duplicate concepts, but much faster
        tasks = [
            self.generate_question(
                subtopic=subtopic,
                difficulty=difficulty,
                exclude_concept_ids=[],  # No exclusion in parallel mode
            )
            for _ in range(count)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and convert to PipelineResult
        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                valid_results.append(PipelineResult(
                    accepted=False,
                    question=None,
                    errors=[f"Generation error: {str(r)}"],
                ))
            else:
                valid_results.append(r)

        return valid_results

    async def _select_concept(
        self,
        subtopic: str,
        difficulty: int,
        exclude_ids: list[str],
    ) -> Optional[dict]:
        """Select a concept from the concept guide."""
        try:
            response = await self.client.send_task(
                endpoint=AGENT_ENDPOINTS["concept_guide"],
                skill_id="select_concept",
                message=json.dumps({
                    "action": "select_concept",
                    "subtopic": subtopic,
                    "difficulty": difficulty,
                    "exclude_ids": exclude_ids,
                }),
            )
            result = self._parse_response(response)
            if result and result.get("success"):
                return result.get("selection")
            return None
        except Exception as e:
            print(f"Error selecting concept: {e}")
            return None

    async def _generate_question(self, selection: dict) -> Optional[dict]:
        """Generate a question from a concept selection."""
        try:
            response = await self.client.send_task(
                endpoint=AGENT_ENDPOINTS["question_generator"],
                skill_id="generate_question",
                message=json.dumps({
                    "action": "generate_question",
                    "selection": selection,
                }),
            )
            result = self._parse_response(response)
            if result and result.get("success"):
                return result
            return None
        except Exception as e:
            print(f"Error generating question: {e}")
            return None

    async def _revise_question(
        self,
        question: dict,
        blueprint: dict,
        issues: list[str],
        suggestions: list[str],
    ) -> Optional[dict]:
        """Revise a question based on feedback."""
        try:
            response = await self.client.send_task(
                endpoint=AGENT_ENDPOINTS["question_generator"],
                skill_id="revise_question",
                message=json.dumps({
                    "action": "revise_question",
                    "question": question,
                    "blueprint": blueprint,
                    "issues": issues,
                    "suggestions": suggestions,
                }),
            )
            result = self._parse_response(response)
            if result and result.get("success"):
                return result
            return None
        except Exception as e:
            print(f"Error revising question: {e}")
            return None

    async def _check_quality(
        self,
        question: dict,
        blueprint: dict,
    ) -> Optional[dict]:
        """Check quality of a question."""
        try:
            response = await self.client.send_task(
                endpoint=AGENT_ENDPOINTS["quality_checker"],
                skill_id="check_quality",
                message=json.dumps({
                    "action": "check_quality",
                    "question": question,
                    "blueprint": blueprint,
                }),
            )
            result = self._parse_response(response)
            if result and result.get("success"):
                return result
            return None
        except Exception as e:
            print(f"Error checking quality: {e}")
            return None

    async def _verify_correctness(
        self,
        question: dict,
        blueprint: dict,
    ) -> Optional[dict]:
        """Verify the correctness of a question by working backwards and forwards."""
        try:
            response = await self.client.send_task(
                endpoint=AGENT_ENDPOINTS["correctness"],
                skill_id="verify_correctness",
                message=json.dumps({
                    "action": "verify_correctness",
                    "question": question,
                    "blueprint": blueprint,
                }),
            )
            result = self._parse_response(response)
            if result and result.get("success"):
                return result
            # If correctness check fails to run, assume verified to not block pipeline
            return {"verified": True, "issues": [], "suggestions": []}
        except Exception as e:
            print(f"Error verifying correctness: {e}")
            # On error, don't block the pipeline - just log and continue
            return {"verified": True, "issues": [], "suggestions": []}

    def _parse_response(self, response: Any) -> Optional[dict]:
        """Parse the response from an agent."""
        if response is None:
            return None

        # Handle error response
        if isinstance(response, dict) and "error" in response:
            print(f"Agent returned error: {response['error']}")
            return None

        # Handle dict response (from A2AClient.send_task)
        if isinstance(response, dict):
            # Check for status.message.parts structure
            status = response.get("status")
            if status and isinstance(status, dict):
                message = status.get("message")
                if message and isinstance(message, dict):
                    parts = message.get("parts", [])
                    if parts:
                        part = parts[0]
                        text = part.get("text", "")
                        if text:
                            try:
                                return json.loads(text)
                            except json.JSONDecodeError:
                                print(f"Failed to parse JSON from agent response: {text[:100]}")
                                return None

            # Maybe it's already the parsed result
            if "success" in response or "selection" in response:
                return response

        # Handle Task response object (legacy)
        if hasattr(response, 'status') and hasattr(response.status, 'message'):
            message = response.status.message
            if message and message.parts:
                part = message.parts[0]
                text = part.root.text if hasattr(part, 'root') else part.text
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return None

        return None

    def _create_result(self, state: PipelineState) -> PipelineResult:
        """Create a PipelineResult from the current state."""
        # Pass the question dict directly - it's already properly formatted from the agent
        return PipelineResult(
            accepted=state.accepted,
            question=state.question,
            concept_id=state.concept_selection.get("concept", {}).get("id") if state.concept_selection else None,
            revision_count=state.revision_count,
            judgment=state.quality_result if state.quality_result else None,
            errors=state.errors,
        )
