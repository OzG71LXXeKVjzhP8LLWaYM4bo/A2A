"""Quality Checker Agent - combines solving, adversarial testing, and judgment."""

import asyncio
import json
from typing import Any, Optional

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from models import (
    JudgmentStatus,
    AttackType,
    Severity,
    QuestionTypeEnum,
)
from config import config


class QualityCheckerAgent(BaseAgent):
    """Agent that solves, attacks, and judges questions for quality."""

    def __init__(self):
        agent_config = AgentConfig(
            name="QualityCheckerAgent",
            description="Verifies question correctness, finds vulnerabilities, and scores quality",
            port=config.ports.quality_checker,
            skills=[
                {
                    "id": "check_quality",
                    "name": "Check Quality",
                    "description": "Comprehensive quality check: solve, attack, and judge",
                    "tags": ["quality", "verification"],
                },
            ],
        )
        super().__init__(agent_config)

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming task requests."""
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

        if action == "check_quality":
            return await self.check_quality(
                question=task_data.get("question", {}),
                blueprint=task_data.get("blueprint", {}),
            )
        else:
            return {"error": f"Unknown action: {action}"}

    async def check_quality(self, question: dict, blueprint: dict) -> dict:
        """Perform comprehensive quality check on a question."""
        try:
            prompt = self._build_quality_check_prompt(question, blueprint)

            result_data = await self.generate_json(prompt, temperature=0.3)

            if not result_data:
                return {"success": False, "error": "Failed to check quality"}

            # Determine final status based on question type
            question_type = question.get('type', 'multiple-choice')
            status = self._determine_status(result_data, question_type)

            # Determine answer correctness based on type
            if question_type == QuestionTypeEnum.DRAG_AND_DROP.value:
                answer_matches = result_data.get("order_is_correct", False)
            elif question_type == QuestionTypeEnum.CLOZE.value:
                answer_matches = result_data.get("blanks_correct", False)
            else:
                answer_matches = str(result_data.get("solved_answer_id")) == "1"

            return {
                "success": True,
                "question_type": question_type,
                # Solver results
                "solution": {
                    "steps": result_data.get("solution_steps", []),
                    "selected_answer_id": result_data.get("solved_answer_id"),
                    "solved_order": result_data.get("solved_order"),
                    "solved_blanks": result_data.get("solved_blanks"),
                    "confidence": result_data.get("solve_confidence", 0.5),
                },
                "answer_matches": answer_matches,
                # Adversarial results
                "vulnerabilities": result_data.get("vulnerabilities", []),
                "can_shortcut": result_data.get("can_solve_without_understanding", False),
                "vulnerability_score": result_data.get("vulnerability_score", 0.0),
                # Judgment results
                "scores": {
                    "clarity": result_data.get("clarity_score", 0.5),
                    "difficulty_match": result_data.get("difficulty_match", True),
                    "actual_difficulty": result_data.get("actual_difficulty", blueprint.get("difficulty_target", 3)),
                    "alignment": result_data.get("alignment_score", 0.5),
                },
                "status": status.value,
                "accepted": status == JudgmentStatus.ACCEPTED,
                "issues": result_data.get("issues", []),
                "suggestions": result_data.get("revision_suggestions", []),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _build_quality_check_prompt(self, question: dict, blueprint: dict) -> str:
        """Build comprehensive quality check prompt based on question type."""
        question_type = question.get('type', 'multiple-choice')

        content_text = question.get('content', '')
        if content_text:
            content_section = f"\n## Question Context/Setup\n{content_text}\n"
        else:
            content_section = ""

        # Build type-specific choices section and correctness criteria
        if question_type == QuestionTypeEnum.DRAG_AND_DROP.value:
            return self._build_drag_drop_prompt(question, blueprint, content_section)
        elif question_type == QuestionTypeEnum.CLOZE.value:
            return self._build_cloze_prompt(question, blueprint, content_section)
        else:
            return self._build_mcq_prompt(question, blueprint, content_section)

    def _build_mcq_prompt(self, question: dict, blueprint: dict, content_section: str) -> str:
        """Build quality check prompt for MCQ questions."""
        choices_text = ""
        for c in question.get("choices", []):
            # Handle both dict and Pydantic model cases
            if isinstance(c, dict):
                c_id = c.get('id', '?')
                c_text = c.get('text', 'Unknown')
            else:
                c_id = getattr(c, 'id', '?')
                c_text = getattr(c, 'text', 'Unknown')
            choices_text += f"  ({c_id}) {c_text}\n"

        return f"""You are a STRICT quality checker for NSW Selective Schools exam questions.
This exam selects the TOP 5% of Year 6 students - questions must be GENUINELY DIFFICULT.
{content_section}
## Question to Check
{question.get('question', 'No question provided')}

## Options
{choices_text}

## Expected Correct Answer: Option 1

## Blueprint Info
- Concept: {blueprint.get('concept_name', 'Unknown')}
- Target Difficulty: {blueprint.get('difficulty_target', 3)}/3 (MUST be genuinely hard for difficulty 3)

## Your Tasks

### 1. SOLVE the question step-by-step
- Work through the problem methodically
- Count how many distinct reasoning steps are required
- Determine which answer you arrive at
- Note if the expected answer (Option 1) matches your solution

### 2. DIFFICULTY CHECK (CRITICAL)
BE HONEST: Is this question genuinely difficult for a Year 6 student?

Signs the question is TOO EASY (any of these = fail):
- Can be solved in 1-2 obvious steps
- Correct answer is clearly different from wrong answers
- Wrong answers are obviously implausible
- Pattern or answer is immediately visible
- A typical Year 6 student would get this right in under 30 seconds
- Only requires reading comprehension, not complex reasoning

Signs of appropriate difficulty:
- Requires 4+ distinct logical steps
- At least 2 wrong answers are very tempting
- Requires careful analysis to eliminate plausible-looking wrong answers
- Includes information that seems relevant but isn't (tests discernment)
- Most Year 6 students would get this wrong

### 3. ATTACK the question (find vulnerabilities)
- Can a student guess correctly without understanding?
- Are there shortcuts (pattern matching, elimination, length clues)?
- Is there any ambiguity that could lead to multiple valid answers?
- Are any distractors obviously wrong or implausible?

### 4. JUDGE the question quality
- Is the language clear and unambiguous?
- Does the difficulty ACTUALLY match the target?
- Does it test the intended concept?

## Output Format
Return a JSON object:

{{
    "solution_steps": [
        {{"step": 1, "action": "What you did", "result": "What you found"}}
    ],
    "num_reasoning_steps": 4,
    "solved_answer_id": "1",
    "solve_confidence": 0.95,
    "time_to_solve_estimate": "60+ seconds",

    "difficulty_assessment": {{
        "is_too_easy": false,
        "reasons_too_easy": [],
        "num_tempting_wrong_answers": 2,
        "estimated_year6_success_rate": "20-30%"
    }},

    "vulnerabilities": [
        {{
            "type": "shortcut|ambiguity|elimination|weak_distractor|too_easy",
            "severity": "critical|major|minor",
            "description": "What the vulnerability is",
            "affected_options": ["2", "3"]
        }}
    ],
    "can_solve_without_understanding": false,
    "vulnerability_score": 0.2,

    "clarity_score": 0.9,
    "alignment_score": 0.85,
    "actual_difficulty": 3,
    "difficulty_match": true,

    "issues": ["List of problems found"],
    "revision_suggestions": ["How to fix each issue - be specific about making it harder"],
    "verdict": "accept|needs_revision|reject"
}}

## Decision Rules (STRICT)
- REJECT if: solved_answer_id != "1", or critical vulnerability, or clarity < 0.5
- REJECT if: is_too_easy = true (question doesn't meet difficulty 3 standard)
- REJECT if: estimated_year6_success_rate > 40%
- NEEDS_REVISION if: num_reasoning_steps < 4, or less than 2 tempting wrong answers
- NEEDS_REVISION if: major vulnerabilities, or minor clarity issues
- ACCEPT if: answer correct, genuinely difficult, no critical issues, clarity > 0.7

BE STRICT. If a question seems straightforward, it's probably too easy. Reject or request revision.

Output ONLY the JSON object."""

    def _build_drag_drop_prompt(self, question: dict, blueprint: dict, content_section: str) -> str:
        """Build quality check prompt for drag-and-drop questions."""
        choices = question.get("choices", [])
        items_text = ""
        correct_order = []
        for c in choices:
            # Handle both dict and Pydantic model cases
            if isinstance(c, dict):
                pos = c.get('correct_position')
                c_id = c.get('id', '?')
                c_text = c.get('text', 'Unknown')
            else:
                pos = getattr(c, 'correct_position', None)
                c_id = getattr(c, 'id', '?')
                c_text = getattr(c, 'text', 'Unknown')

            if pos is not None:
                correct_order.append((pos, c_id, c_text))
            items_text += f"  ({c_id}) {c_text} [position: {pos}]\n"

        correct_order.sort(key=lambda x: x[0])
        expected_order = " -> ".join([f"({item[1]}) {item[2][:30]}..." for item in correct_order])

        return f"""You are a STRICT quality checker for NSW Selective Schools exam questions.
This exam selects the TOP 5% of Year 6 students - questions must be GENUINELY DIFFICULT.
{content_section}
## Question to Check (DRAG-AND-DROP / SEQUENCING)
{question.get('question', 'No question provided')}

## Items to Order
{items_text}

## Expected Correct Order
{expected_order}

## Blueprint Info
- Concept: {blueprint.get('concept_name', 'Unknown')}
- Target Difficulty: {blueprint.get('difficulty_target', 3)}/3

## Your Tasks

### 1. VERIFY the sequence
- Is the expected order logically correct?
- Work through why each item belongs in its position
- Check if any items could reasonably be in different positions

### 2. DIFFICULTY CHECK
- Is the ordering non-obvious and require reasoning?
- Are there any "obviously first" or "obviously last" items? (bad)
- Could students guess the order without understanding?
- Are distractors (null position) plausible enough to confuse?

### 3. ATTACK the question
- Can position be guessed from keywords or patterns?
- Is there temporal/logical ambiguity?
- Are any positions too obvious?

### 4. JUDGE quality
- Is the context clear?
- Is there exactly one valid ordering?
- Does it test sequencing skills appropriately?

## Output Format
{{
    "solution_steps": [{{"step": 1, "action": "...", "result": "..."}}],
    "num_reasoning_steps": 4,
    "order_is_correct": true,
    "solved_order": ["1", "2", "3", "4", "5"],
    "solve_confidence": 0.95,

    "difficulty_assessment": {{
        "is_too_easy": false,
        "reasons_too_easy": [],
        "num_ambiguous_positions": 0,
        "estimated_year6_success_rate": "20-30%"
    }},

    "vulnerabilities": [...],
    "can_solve_without_understanding": false,
    "vulnerability_score": 0.2,

    "clarity_score": 0.9,
    "alignment_score": 0.85,
    "actual_difficulty": 3,
    "difficulty_match": true,

    "issues": [...],
    "revision_suggestions": [...],
    "verdict": "accept|needs_revision|reject"
}}

Output ONLY the JSON object."""

    def _build_cloze_prompt(self, question: dict, blueprint: dict, content_section: str) -> str:
        """Build quality check prompt for cloze (fill-in-the-blank) questions."""
        choices = question.get("choices", [])
        blanks_text = ""
        for c in choices:
            # Handle both dict and Pydantic model cases
            if isinstance(c, dict):
                options = c.get('options', [])
                correct_idx = c.get('is_correct', 0)
                c_id = c.get('id', '?')
            else:
                options = getattr(c, 'options', []) or []
                correct_idx = getattr(c, 'is_correct', 0) or 0
                c_id = getattr(c, 'id', '?')

            correct_answer = options[correct_idx] if options and isinstance(correct_idx, int) and 0 <= correct_idx < len(options) else "?"
            blanks_text += f"  Blank {c_id}: Options {options}, Correct: {correct_answer} (index {correct_idx})\n"

        return f"""You are a STRICT quality checker for NSW Selective Schools exam questions.
This exam selects the TOP 5% of Year 6 students - questions must be GENUINELY DIFFICULT.

## Question to Check (CLOZE / FILL-IN-THE-BLANK)
{question.get('question', 'No question provided')}

## Content with Blanks
{question.get('content', 'No content')}

## Blank Options and Answers
{blanks_text}

## Blueprint Info
- Concept: {blueprint.get('concept_name', 'Unknown')}
- Target Difficulty: {blueprint.get('difficulty_target', 3)}/3

## Your Tasks

### 1. VERIFY each blank
- Are the correct answers actually correct?
- Work through the logic for each blank
- Check if any wrong options could also be valid

### 2. DIFFICULTY CHECK
- Are the wrong options plausible?
- Does solving require understanding the pattern/concept?
- Could students guess correctly without reasoning?

### 3. ATTACK the question
- Can blanks be solved independently or do they require connected reasoning?
- Are any wrong options obviously wrong?
- Is there only one valid answer for each blank?

### 4. JUDGE quality
- Is the pattern/sequence clear but non-trivial?
- Do options provide good distractors?

## Output Format
{{
    "solution_steps": [{{"step": 1, "action": "...", "result": "..."}}],
    "num_reasoning_steps": 4,
    "blanks_correct": true,
    "solved_blanks": {{"1": 0, "2": 1}},
    "solve_confidence": 0.95,

    "difficulty_assessment": {{
        "is_too_easy": false,
        "reasons_too_easy": [],
        "estimated_year6_success_rate": "20-30%"
    }},

    "vulnerabilities": [...],
    "can_solve_without_understanding": false,
    "vulnerability_score": 0.2,

    "clarity_score": 0.9,
    "alignment_score": 0.85,
    "actual_difficulty": 3,
    "difficulty_match": true,

    "issues": [...],
    "revision_suggestions": [...],
    "verdict": "accept|needs_revision|reject"
}}

Output ONLY the JSON object."""

    def _determine_status(self, result_data: dict, question_type: str = "multiple-choice") -> JudgmentStatus:
        """Determine final judgment status from results."""
        # Check correctness based on question type
        if question_type == QuestionTypeEnum.DRAG_AND_DROP.value:
            if not result_data.get("order_is_correct", False):
                return JudgmentStatus.REJECTED
        elif question_type == QuestionTypeEnum.CLOZE.value:
            if not result_data.get("blanks_correct", False):
                return JudgmentStatus.REJECTED
        else:
            # MCQ: Check if answer is wrong
            if str(result_data.get("solved_answer_id")) != "1":
                return JudgmentStatus.REJECTED

        # Check verdict
        verdict = result_data.get("verdict", "accept")
        if verdict == "reject":
            return JudgmentStatus.REJECTED
        elif verdict == "needs_revision":
            return JudgmentStatus.NEEDS_REVISION

        # Check difficulty assessment - REJECT if too easy
        difficulty_assessment = result_data.get("difficulty_assessment", {})
        if difficulty_assessment.get("is_too_easy", False):
            return JudgmentStatus.REJECTED

        # Check estimated success rate - should be low for hard questions
        success_rate = difficulty_assessment.get("estimated_year6_success_rate", "50%")
        if isinstance(success_rate, str):
            # Parse "20-30%" or "40%" format
            try:
                rate_num = int(success_rate.replace("%", "").split("-")[0])
                if rate_num > 40:
                    return JudgmentStatus.NEEDS_REVISION
            except (ValueError, IndexError):
                pass

        # Check number of reasoning steps
        num_steps = result_data.get("num_reasoning_steps", 0)
        if num_steps < 3:
            return JudgmentStatus.NEEDS_REVISION

        # Check for critical vulnerabilities
        for vuln in result_data.get("vulnerabilities", []):
            if vuln.get("severity") == "critical":
                return JudgmentStatus.REJECTED
            elif vuln.get("severity") == "major":
                return JudgmentStatus.NEEDS_REVISION
            # Check for "too_easy" vulnerability type
            if vuln.get("type") == "too_easy":
                return JudgmentStatus.NEEDS_REVISION

        # Check scores
        if result_data.get("clarity_score", 0) < 0.5:
            return JudgmentStatus.REJECTED
        elif result_data.get("clarity_score", 0) < 0.7:
            return JudgmentStatus.NEEDS_REVISION

        if result_data.get("vulnerability_score", 0) > 0.6:
            return JudgmentStatus.NEEDS_REVISION

        return JudgmentStatus.ACCEPTED


async def main():
    """Run the Quality Checker Agent."""
    agent = QualityCheckerAgent()
    print(f"Starting Quality Checker Agent on port {config.ports.quality_checker}...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
