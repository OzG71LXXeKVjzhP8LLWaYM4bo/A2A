"""Question Generator Agent - combines blueprint planning and surface realization."""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from models import (
    QuestionBlueprint,
    QuestionType,
    TargetSkill,
    DistractorSpec,
    SolutionStep,
    Question,
    Choice,
    QuestionTypeEnum,
)
from config import config

# Paths to prompts directories by topic
PROMPTS_DIRS = {
    "thinking_skills": Path(__file__).parent.parent / "prompts" / "thinking-skills" / "subtopics",
    "math": Path(__file__).parent.parent / "prompts" / "math" / "subtopics",
}
# Backwards compatible default
PROMPTS_DIR = PROMPTS_DIRS["thinking_skills"]


class QuestionGeneratorAgent(BaseAgent):
    """Agent that creates question blueprints and realizes them into polished questions."""

    def __init__(self):
        agent_config = AgentConfig(
            name="QuestionGeneratorAgent",
            description="Creates blueprints and generates polished NSW Selective exam questions",
            port=config.ports.question_generator,
            skills=[
                {
                    "id": "generate_question",
                    "name": "Generate Question",
                    "description": "Generate a complete question from a concept selection",
                    "tags": ["generation", "question"],
                },
                {
                    "id": "revise_question",
                    "name": "Revise Question",
                    "description": "Revise a question based on feedback",
                    "tags": ["generation", "revision"],
                },
            ],
        )
        super().__init__(agent_config)
        self._prompt_cache: dict[str, str] = {}

    def _load_subtopic_prompt(self, subtopic_name: str, topic: str = "thinking_skills") -> Optional[str]:
        """Load the subtopic-specific prompt from markdown files.

        Args:
            subtopic_name: The subtopic name (e.g., "Geometry", "Logical Reasoning")
            topic: The topic namespace ("thinking_skills" or "math")
        """
        cache_key = f"{topic}:{subtopic_name}"
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        # Convert subtopic name to filename (e.g., "Logical Reasoning" -> "logical_reasoning.md")
        filename = subtopic_name.lower().replace(" ", "_").replace("&", "and") + ".md"

        # Try the topic-specific directory first
        prompts_dir = PROMPTS_DIRS.get(topic, PROMPTS_DIR)
        prompt_path = prompts_dir / filename

        if prompt_path.exists():
            content = prompt_path.read_text()
            self._prompt_cache[cache_key] = content
            return content
        return None

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

        if action == "generate_question":
            return await self.generate_question(task_data.get("selection", {}))
        elif action == "revise_question":
            return await self.revise_question(
                question=task_data.get("question", {}),
                blueprint=task_data.get("blueprint", {}),
                issues=task_data.get("issues", []),
                suggestions=task_data.get("suggestions", []),
            )
        else:
            return {"error": f"Unknown action: {action}"}

    def _detect_topic(self, concept_data: dict) -> str:
        """Detect the topic from concept data (thinking_skills or math)."""
        topic_name = concept_data.get("topic_name", "").lower()
        if "math" in topic_name:
            return "math"
        return "thinking_skills"

    async def generate_question(self, selection_data: dict) -> dict:
        """Generate a complete question from a concept selection."""
        try:
            concept_data = selection_data.get("concept", {})
            target_difficulty = selection_data.get("target_difficulty", 3)
            target_bloom = selection_data.get("target_bloom_level", "application")
            selected_misconceptions = selection_data.get("selected_misconceptions", [])
            selected_pattern = selection_data.get("selected_pattern")

            # Detect topic (thinking_skills or math)
            topic = self._detect_topic(concept_data)

            # Generate blueprint and question in one prompt
            prompt = self._build_generation_prompt(
                concept_data=concept_data,
                target_difficulty=target_difficulty,
                target_bloom=target_bloom,
                selected_misconceptions=selected_misconceptions,
                selected_pattern=selected_pattern,
                topic=topic,
            )

            result_data = await self.generate_json(prompt, temperature=0.7)

            if not result_data:
                return {"success": False, "error": "Failed to generate question"}

            # Parse into models
            blueprint = self._parse_blueprint(result_data, concept_data, target_difficulty, topic)
            question = self._parse_question(result_data, blueprint, topic)

            return {
                "success": True,
                "blueprint": blueprint.model_dump(mode="json"),
                "question": question.model_dump(mode="json"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def revise_question(
        self,
        question: dict,
        blueprint: dict,
        issues: list[str],
        suggestions: list[str],
    ) -> dict:
        """Revise a question based on feedback."""
        try:
            prompt = self._build_revision_prompt(question, blueprint, issues, suggestions)

            result_data = await self.generate_json(prompt, temperature=0.5)

            if not result_data:
                return {"success": False, "error": "Failed to revise question"}

            # Parse revised blueprint and question
            concept_data = {
                "id": blueprint.get("concept_id"),
                "name": blueprint.get("concept_name"),
                "subtopic_id": blueprint.get("subtopic_id"),
                "subtopic_name": blueprint.get("subtopic_name"),
            }

            revised_blueprint = self._parse_blueprint(
                result_data,
                concept_data,
                blueprint.get("difficulty_target", 3),
            )
            revised_blueprint.revision_count = blueprint.get("revision_count", 0) + 1

            revised_question = self._parse_question(result_data, revised_blueprint)

            return {
                "success": True,
                "blueprint": revised_blueprint.model_dump(mode="json"),
                "question": revised_question.model_dump(mode="json"),
                "revision_count": revised_blueprint.revision_count,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _determine_question_type(self, subtopic_name: str, concept_data: dict) -> str:
        """Determine the appropriate question type based on subtopic.

        Note: Thinking Skills and Math are ALWAYS multiple-choice.
        Cloze, drag-and-drop, and other types are for English/Reading only.
        """
        # Thinking Skills and Math are always multiple-choice
        # Spatial Reasoning may have images but is still MCQ format
        return QuestionTypeEnum.MULTIPLE_CHOICE.value

    def _build_generation_prompt(
        self,
        concept_data: dict,
        target_difficulty: int,
        target_bloom: str,
        selected_misconceptions: list[str],
        selected_pattern: str = None,
        topic: str = "thinking_skills",
    ) -> str:
        """Build the prompt for question generation using NSW exam formats."""
        subtopic_name = concept_data.get('subtopic_name', 'Unknown')
        subtopic_prompt = self._load_subtopic_prompt(subtopic_name, topic)

        # Use topic-specific builder
        if topic == "math":
            return self._build_math_prompt(
                concept_data=concept_data,
                target_difficulty=target_difficulty,
                target_bloom=target_bloom,
                selected_misconceptions=selected_misconceptions,
                selected_pattern=selected_pattern,
                subtopic_prompt=subtopic_prompt,
            )

        difficulty_desc = {
            1: "EASY - straightforward, 1-2 steps",
            2: "MEDIUM - requires careful thinking, 2-3 steps",
            3: "EXTREMELY HARD - only top 5% of Year 6 students should answer correctly",
        }

        # HARD difficulty requirements - these get inserted into the prompt
        hard_requirements = """
## CRITICAL: MAKE THIS QUESTION GENUINELY DIFFICULT

This is for the NSW Selective Schools exam - a competitive test where only the TOP 5% of students
are selected. Your question must be GENUINELY CHALLENGING, not a straightforward problem.

### Difficulty Requirements (ALL must be met):
1. **Multi-step reasoning**: Require 4+ distinct logical steps that CANNOT be skipped
2. **Hidden complexity**: The answer should NOT be obvious even after reading carefully
3. **Trap answers**: At least 2 wrong answers must seem very plausible and require careful analysis to eliminate
4. **No pattern matching**: Cannot be solved by recognizing a simple pattern or formula
5. **Requires insight**: Student must notice something non-obvious or make a creative connection
6. **Information overload**: Include 4-5 pieces of information where not all are directly relevant
7. **Counter-intuitive**: The correct answer should surprise students who rush

### What makes a question TOO EASY (AVOID these):
- Can be solved in 1-2 obvious steps
- Correct answer is clearly different from wrong answers
- Simple application of a single rule or formula
- Wrong answers are obviously wrong
- Pattern is immediately visible
- Reading comprehension is the main challenge (not reasoning)

### Examples of HARD question techniques:
- Nested conditionals: "If A then B, but only when C is not true, unless D..."
- Exceptions to rules: Give a rule, then add an exception that changes the answer
- Irrelevant information: Include facts that seem important but aren't needed
- Order matters: Require tracking multiple changes in sequence
- Contrapositive reasoning: Require students to think about what must be FALSE
- Multiple valid-looking paths: Several approaches seem right but only one works
"""

        misconceptions_text = "\n".join(f"- {m}" for m in selected_misconceptions) if selected_misconceptions else ""

        requires_image = concept_data.get("typically_requires_image", False)
        image_types = concept_data.get("image_types", [])

        # Build image section based on subtopic requirements
        if subtopic_name == "Deduction":
            image_section = """
## Image Requirement
For Deduction questions, the image shows TWO character portraits side-by-side with names (NO quotes in image).
Character statements go in the content field as HTML, not in the image.
Set requires_image: true and provide image_description in this format:
```
image_type: character_portrait_dual
person1_name: [Name1]
person1_appearance: [brief description]
person2_name: [Name2]
person2_appearance: [brief description]
```"""
        elif subtopic_name == "Inference":
            image_section = """
## Image Requirement
For Inference questions, the image shows a SINGLE character portrait with their name AND their flawed statement.
Set requires_image: true and provide image_description in this format:
```
image_type: character_portrait_single
person_name: [Name]
person_appearance: [brief description]
person_statement: "[Their exact flawed statement]"
```"""
        elif requires_image:
            image_section = f"""
## Image Requirement
This question type may require an image.
Suitable image types: {', '.join(image_types) if image_types else 'diagram, figure, or visual'}
If using an image, set requires_image: true and describe in image_description."""
        else:
            image_section = """
## Image Requirement
This question should be text-only. Set requires_image: false."""

        # Build subtopic-specific format instructions
        if subtopic_name == "Deduction":
            format_instructions = """
## OUTPUT FORMAT (NSW Selective Exam - Deduction)

For Deduction questions, use this EXACT structure:

{
    "setup_elements": ["premise description", "character claims"],
    "question_stem_structure": "Whose reasoning is correct?",
    "constraints": ["logical constraints being tested"],
    "correct_answer_reasoning": "Explanation of correct logic",
    "solution_steps": [{"step_number": 1, "description": "...", "reasoning": "..."}],
    "requires_image": true,
    "image_spec": "image_type: character_portrait_dual\\nperson1_name: [Name1]\\nperson1_appearance: [description]\\nperson2_name: [Name2]\\nperson2_appearance: [description]",
    "content": "<div style=\\"border: 1px solid black; padding: 12px; margin-bottom: 12px;\\"><p>PREMISE TEXT HERE</p></div>\\n\\n<p><strong>[Name1]:</strong> \\"[Their statement]\\"</p>\\n<p><strong>[Name2]:</strong> \\"[Their statement]\\"</p>",
    "question_text": "If the information in the box is true, whose reasoning is correct?",
    "choices": [
        {"id": "1", "text": "[Name1] only"},
        {"id": "2", "text": "[Name2] only"},
        {"id": "3", "text": "Both [Name1] and [Name2]"},
        {"id": "4", "text": "Neither [Name1] nor [Name2]"}
    ],
    "explanation": "Explanation with <strong>HTML</strong> formatting",
    "tags": ["Thinking Skills", "Deduction"]
}

Character name pairs to use: Sara & Mila, Will & Evie, Jack & Amelia, Yifan & Ria, Alex & Jordan, Marcus & Leila"""
        elif subtopic_name == "Inference":
            format_instructions = """
## OUTPUT FORMAT (NSW Selective Exam - Inference)

For Inference questions, use this EXACT structure with HTML box:

{
    "setup_elements": ["premise/rule context"],
    "question_stem_structure": "Which sentence shows the mistake [Name] has made?",
    "constraints": ["what the person incorrectly concluded"],
    "correct_answer_reasoning": "Why this is the logical error",
    "solution_steps": [{"step_number": 1, "description": "...", "reasoning": "..."}],
    "requires_image": true,
    "image_spec": "image_type: character_portrait_single\\nperson_name: [Name]\\nperson_appearance: [description]\\nperson_statement: \\"[Their flawed statement]\\"",
    "content": "<div style=\\"border: 1px solid black; padding: 12px; margin-bottom: 12px;\\"><p>THE RULE OR PREMISE HERE</p></div>\\n\\n<p><strong>[Name]:</strong> \\"[Their flawed conclusion based on the rule]\\"</p>",
    "question_text": "Which one of the following sentences shows the mistake [Name] has made?",
    "choices": [
        {"id": "1", "text": "Correct identification of the logical error"},
        {"id": "2", "text": "Plausible but incorrect analysis"},
        {"id": "3", "text": "Misidentifies the error type"},
        {"id": "4", "text": "Irrelevant to the actual mistake"}
    ],
    "explanation": "Explanation with <strong>HTML</strong> formatting",
    "tags": ["Thinking Skills", "Inference"]
}

Character names to use: Sam, Ferdinand, Jarrah, Lisa, Alex, Maya, Noah, Priya, Marcus, Zara"""
        elif subtopic_name == "Critical Thinking":
            format_instructions = """
## OUTPUT FORMAT (NSW Selective Exam - Critical Thinking)

For Critical Thinking (strengthen/weaken argument) questions:

{
    "setup_elements": ["argument/claim being made"],
    "question_stem_structure": "Which statement strengthens/weakens the argument?",
    "constraints": ["what would support or undermine the claim"],
    "correct_answer_reasoning": "Why this option affects the argument",
    "solution_steps": [{"step_number": 1, "description": "...", "reasoning": "..."}],
    "requires_image": false,
    "image_spec": null,
    "content": "The argument or claim being made (context)",
    "question_text": "Which statement, if true, most [strengthens/weakens] the argument above?",
    "choices": [
        {"id": "1", "text": "Statement that most strengthens/weakens"},
        {"id": "2", "text": "Irrelevant or neutral statement"},
        {"id": "3", "text": "Statement that has opposite effect"},
        {"id": "4", "text": "Plausible but doesn't affect argument"}
    ],
    "explanation": "Explanation with <strong>HTML</strong> formatting",
    "tags": ["Thinking Skills", "Critical Thinking"]
}"""
        elif subtopic_name == "Logical Reasoning":
            format_instructions = """
## OUTPUT FORMAT (NSW Selective Exam - Logical Reasoning)

For Logical Reasoning (constraint satisfaction / logic puzzles), you MUST split content and question:

{
    "setup_elements": ["puzzle scenario", "what needs to be determined"],
    "question_stem_structure": "Determine the correct arrangement/order/pairing",
    "constraints": ["clue 1", "clue 2", "clue 3", "clue 4"],
    "correct_answer_reasoning": "Step-by-step logical deduction",
    "solution_steps": [{"step_number": 1, "description": "...", "reasoning": "..."}],
    "requires_image": false,
    "image_spec": null,
    "content": "PUZZLE SETUP AND ALL CLUES GO HERE.\\n\\nExample format:\\nFive students – Amelia, Ben, Chloe, Daniel, and Emily – each chose a different activity.\\n\\n• Clue 1: Amelia doesn't like sports.\\n• Clue 2: Ben attends swimming.\\n• Clue 3: Chloe is in the cricket team.\\n• Clue 4: Daniel is not in Mr. Carter's class.",
    "question_text": "Which of the following statements must be true?",
    "choices": [
        {"id": "1", "text": "Correct deduction from clues"},
        {"id": "2", "text": "Plausible but contradicts a clue"},
        {"id": "3", "text": "Could be true but not necessarily"},
        {"id": "4", "text": "Contradicts multiple clues"}
    ],
    "explanation": "Step-by-step explanation with <strong>HTML</strong> formatting",
    "tags": ["Thinking Skills", "Logical Reasoning"]
}

CRITICAL: The 'content' field MUST contain the puzzle setup and ALL clues. The 'question_text' field should ONLY contain the question being asked (e.g., "Which statement must be true?"). Do NOT put clues in question_text."""
        elif subtopic_name == "Numerical Reasoning":
            format_instructions = """
## OUTPUT FORMAT (NSW Selective Exam - Numerical Reasoning)

For Numerical Reasoning (number patterns, sequences, mathematical logic):

{
    "setup_elements": ["pattern or sequence context", "what needs to be found"],
    "question_stem_structure": "Find the pattern / next number / missing value",
    "constraints": ["pattern rules", "given values"],
    "correct_answer_reasoning": "How the pattern works",
    "solution_steps": [{"step_number": 1, "description": "...", "reasoning": "..."}],
    "requires_image": false,
    "image_spec": null,
    "content": "THE PROBLEM SETUP GOES HERE.\\n\\nExample: A sequence follows a specific rule. The first five terms are:\\n2, 6, 18, 54, 162\\n\\nAnother example: In a number grid, each row and column follows a pattern.",
    "question_text": "What is the next number in the sequence?",
    "choices": [
        {"id": "1", "text": "Correct answer"},
        {"id": "2", "text": "Common arithmetic mistake"},
        {"id": "3", "text": "Wrong pattern identified"},
        {"id": "4", "text": "Calculation error"}
    ],
    "explanation": "Clear explanation with <strong>HTML</strong> formatting showing the pattern",
    "tags": ["Thinking Skills", "Numerical Reasoning"]
}

CRITICAL: The 'content' field MUST contain the sequence, pattern, or problem setup. The 'question_text' should ONLY contain the question. Do NOT put the sequence/pattern in question_text."""
        elif subtopic_name == "Spatial Reasoning":
            format_instructions = """
## OUTPUT FORMAT (NSW Selective Exam - Spatial Reasoning)

For Spatial Reasoning (3D visualization, rotations, views):

{
    "setup_elements": ["spatial scenario", "what transformation/view is needed"],
    "question_stem_structure": "Identify the correct view/rotation/transformation",
    "constraints": ["spatial constraints"],
    "correct_answer_reasoning": "How the spatial transformation works",
    "solution_steps": [{"step_number": 1, "description": "...", "reasoning": "..."}],
    "requires_image": true,
    "image_spec": "Description of 3D structure or spatial diagram needed",
    "content": "A 3D structure is shown. Study the arrangement of blocks/shapes carefully.",
    "question_text": "Which of the following shows the TOP view of this structure?",
    "choices": [
        {"id": "1", "text": "A"},
        {"id": "2", "text": "B"},
        {"id": "3", "text": "C"},
        {"id": "4", "text": "D"}
    ],
    "explanation": "Explanation of spatial reasoning with <strong>HTML</strong> formatting",
    "tags": ["Thinking Skills", "Spatial Reasoning"]
}

CRITICAL: The 'content' field should describe what the student is looking at. The 'question_text' asks what they need to identify."""
        elif subtopic_name == "Pattern Recognition":
            format_instructions = """
## OUTPUT FORMAT (NSW Selective Exam - Pattern Recognition)

For Pattern Recognition (visual/logical patterns, sequences):

{
    "setup_elements": ["pattern context", "what needs to be identified"],
    "question_stem_structure": "Find the next element / missing piece / pattern rule",
    "constraints": ["pattern rules"],
    "correct_answer_reasoning": "How the pattern works",
    "solution_steps": [{"step_number": 1, "description": "...", "reasoning": "..."}],
    "requires_image": false,
    "image_spec": null,
    "content": "THE PATTERN OR SEQUENCE SETUP GOES HERE.\\n\\nExample: Look at the following sequence of shapes/symbols/letters and identify the pattern.",
    "question_text": "What comes next in the pattern?",
    "choices": [
        {"id": "1", "text": "Correct next element"},
        {"id": "2", "text": "Wrong pattern interpretation"},
        {"id": "3", "text": "Partial pattern match"},
        {"id": "4", "text": "Random distractor"}
    ],
    "explanation": "Explanation with <strong>HTML</strong> formatting",
    "tags": ["Thinking Skills", "Pattern Recognition"]
}

CRITICAL: The 'content' field MUST contain the pattern/sequence. The 'question_text' should ONLY ask the question."""
        else:
            format_instructions = f"""
## OUTPUT FORMAT (NSW Selective Exam)

{{
    "setup_elements": ["context element 1", "context element 2"],
    "question_stem_structure": "Template/structure of the question",
    "constraints": ["logical constraint 1", "constraint 2"],
    "correct_answer_reasoning": "Why the correct answer is right",
    "solution_steps": [{{"step_number": 1, "description": "First step", "reasoning": "Why needed"}}],
    "requires_image": {str(requires_image).lower()},
    "image_spec": {"'Description of needed image'" if requires_image else "null"},
    "content": "Setup/context MUST go here - do NOT set to null",
    "question_text": "The question being asked (NOT the setup)?",
    "choices": [
        {{"id": "1", "text": "Correct answer"}},
        {{"id": "2", "text": "Wrong answer 1", "misconception": "Error that leads here"}},
        {{"id": "3", "text": "Wrong answer 2", "misconception": "Error that leads here"}},
        {{"id": "4", "text": "Wrong answer 3", "misconception": "Error that leads here"}}
    ],
    "explanation": "Clear explanation with <strong>HTML</strong> formatting",
    "tags": ["Thinking Skills", "{subtopic_name}"]
}}

CRITICAL: The 'content' field should contain the problem setup/context. The 'question_text' should only contain the actual question."""

        # Build the complete prompt
        prompt = f"""You are creating a NSW Selective Schools exam question (Year 6 level, Thinking Skills).

## Concept to Test
- **Name**: {concept_data.get('name', 'Unknown')}
- **Description**: {concept_data.get('description', 'No description')}
- **Subtopic**: {subtopic_name}

## Target Parameters
- **Difficulty**: {target_difficulty}/3 - {difficulty_desc.get(target_difficulty, 'EXTREMELY HARD')}
- **Cognitive Level**: {target_bloom}
- **Question Type**: Multiple Choice (4 options)
"""

        # Add hard difficulty requirements for difficulty 3
        if target_difficulty >= 3:
            prompt += hard_requirements

        # Add subtopic-specific instructions if available
        if subtopic_prompt:
            prompt += f"""
## Subtopic-Specific Guidelines
{subtopic_prompt}
"""

        if misconceptions_text:
            prompt += f"""
## Distractor Design (MAKE THESE TRICKY)
Wrong answers must be VERY plausible - students should have to think hard to eliminate them:
{misconceptions_text}
"""

        prompt += image_section
        prompt += format_instructions

        prompt += """

## CRITICAL RULES
1. Choice id="1" MUST be the correct answer
2. Question must have exactly ONE correct answer
3. Language: clear, unambiguous, Year 6 appropriate vocabulary (but HARD reasoning)
4. NEVER use literal \\n in content - use actual line breaks or <br> tags
5. For Deduction: Use HTML box format with character statements
6. For Inference: Use HTML box format with premise and character statement
7. All explanations should use <strong>HTML</strong> for emphasis
8. THIS MUST BE A GENUINELY DIFFICULT QUESTION - if a typical Year 6 student can solve it quickly, it's TOO EASY

## AUSTRALIAN CONTEXT (MANDATORY)
- Use AUSTRALIAN ENGLISH spelling: colour, favourite, organisation, travelled, centre, metre, litre, programme
- All locations MUST be Australian: Sydney, Melbourne, Brisbane, Perth, Adelaide, Canberra, Hobart, Darwin
- Use Australian suburbs: Parramatta, Bondi, St Kilda, Surry Hills, Manly, Fremantle, Paddington
- Australian schools: use names like "Northwood Primary", "Riverside Public School", "St Mary's College"
- Australian currency: dollars and cents ($, AUD)
- Australian seasons: Summer (Dec-Feb), Autumn (Mar-May), Winter (Jun-Aug), Spring (Sep-Nov)
- Australian animals/plants when relevant: kangaroo, koala, platypus, wombat, eucalyptus, banksia
- Australian sports: cricket, AFL, rugby league, netball, swimming
- NO American references: no "favorite", "color", "math" (use "maths"), no US cities, no Fahrenheit

Output ONLY the JSON object."""

        return prompt

    def _build_math_prompt(
        self,
        concept_data: dict,
        target_difficulty: int,
        target_bloom: str,
        selected_misconceptions: list[str],
        selected_pattern: str = None,
        subtopic_prompt: str = None,
    ) -> str:
        """Build prompt for NSW Math exam question generation (5 choices, no images)."""
        subtopic_name = concept_data.get('subtopic_name', 'Unknown')
        concept_name = concept_data.get('name', 'Unknown')
        concept_description = concept_data.get('description', '')

        difficulty_desc = {
            1: "EASY - straightforward, 1-2 steps",
            2: "MEDIUM - requires careful thinking, 2-3 steps",
            3: "HARD - multi-step, requires insight, only top students solve correctly",
        }

        misconceptions_text = "\n".join(f"- {m}" for m in selected_misconceptions) if selected_misconceptions else "None provided"

        hard_requirements = """
## CRITICAL: MAKE THIS QUESTION GENUINELY DIFFICULT

This is for the NSW Selective Schools exam - a competitive test where only the TOP 5% of students
are selected. Your question must be GENUINELY CHALLENGING, not a straightforward problem.

### Difficulty Requirements (ALL must be met):
1. **Multi-step reasoning**: Require 3-4 distinct calculation/reasoning steps
2. **Problem interpretation**: The problem setup should require careful reading
3. **Trap answers**: At least 2 wrong answers must result from common mistakes
4. **Not textbook**: Cannot be solved by simple formula application
5. **Real context**: Embed the math in a realistic scenario

### What makes a question TOO EASY (AVOID these):
- Direct formula application (e.g., "What is 3/4 of 24?")
- Single-operation problems
- Obvious correct answer
- Distractors that are clearly wrong
"""

        prompt = f"""You are creating a NSW Selective Schools Mathematics exam question (Year 6 level).

## Concept to Test
- **Concept**: {concept_name}
- **Description**: {concept_description}
- **Subtopic**: {subtopic_name}

## Target Parameters
- **Difficulty**: {target_difficulty}/3 - {difficulty_desc.get(target_difficulty, 'HARD')}
- **Cognitive Level**: {target_bloom}
- **Question Type**: Multiple Choice (5 options A-E)
- **Image**: NOT REQUIRED - text-only question
"""

        if target_difficulty >= 3:
            prompt += hard_requirements

        if subtopic_prompt:
            prompt += f"""
## Subtopic-Specific Guidelines
{subtopic_prompt}
"""

        prompt += f"""
## Common Misconceptions (use for wrong answers)
{misconceptions_text}
"""

        if selected_pattern:
            prompt += f"""
## Question Pattern (use as inspiration, not exactly)
{selected_pattern}
"""

        prompt += """
## OUTPUT FORMAT (NSW Selective Exam - Mathematics)

Return a JSON object with this EXACT structure:

{
    "setup_elements": ["what the problem sets up", "given information"],
    "question_stem_structure": "Template/structure of the question",
    "constraints": ["mathematical constraints"],
    "correct_answer_reasoning": "Step-by-step solution approach",
    "solution_steps": [
        {"step_number": 1, "description": "First step", "reasoning": "Why this step"},
        {"step_number": 2, "description": "Second step", "reasoning": "Why this step"}
    ],
    "requires_image": false,
    "image_spec": null,
    "content": "The problem context/scenario (or null if the question is self-contained)",
    "question_text": "The actual mathematical question being asked?",
    "choices": [
        {"id": "1", "text": "Correct answer"},
        {"id": "2", "text": "Wrong answer based on misconception 1", "misconception": "What error leads here"},
        {"id": "3", "text": "Wrong answer based on misconception 2", "misconception": "What error leads here"},
        {"id": "4", "text": "Wrong answer based on misconception 3", "misconception": "What error leads here"},
        {"id": "5", "text": "Wrong answer based on calculation error", "misconception": "What error leads here"}
    ],
    "explanation": "Clear step-by-step explanation with <strong>HTML</strong> formatting",
    "tags": ["Mathematics", "SUBTOPIC_NAME"]
}

## CRITICAL RULES
1. Choice id="1" MUST be the correct answer
2. Question must have EXACTLY 5 answer choices (not 4!)
3. Question must have exactly ONE correct answer
4. Language: clear, unambiguous, Year 6 appropriate vocabulary
5. NEVER use literal \\n in content - use actual line breaks or <br> tags
6. All explanations should use <strong>HTML</strong> for emphasis
7. requires_image MUST be false (text-only math questions)

## AUSTRALIAN CONTEXT (MANDATORY)
- Use AUSTRALIAN ENGLISH spelling: colour, favourite, organisation, travelled, centre, metre, litre
- All locations MUST be Australian: Sydney, Melbourne, Brisbane, Perth, Adelaide, Canberra
- Use Australian suburbs: Parramatta, Bondi, St Kilda, Surry Hills, Manly, Fremantle
- Australian schools: use names like "Northwood Primary", "Riverside Public School"
- Australian currency: dollars and cents ($, AUD)
- Australian seasons: Summer (Dec-Feb), Autumn (Mar-May), Winter (Jun-Aug), Spring (Sep-Nov)
- Use "maths" not "math"
- Use metric units: metres, centimetres, kilograms, litres
- NO American references: no "favorite", "color", "math", no US cities, no Fahrenheit

## DISTRACTOR DESIGN
Each wrong answer should result from a specific, believable error:
- Misconception-based: Applying a rule incorrectly (e.g., adding denominators when adding fractions)
- Calculation error: Making a plausible arithmetic mistake
- Reading error: Misinterpreting what the question asks
- Step-skipping: Getting a partial answer by skipping a step

Output ONLY the JSON object."""

        return prompt

    def _build_revision_prompt(
        self,
        question: dict,
        blueprint: dict,
        issues: list[str],
        suggestions: list[str],
    ) -> str:
        """Build prompt for question revision."""
        issues_text = "\n".join(f"- {i}" for i in issues) if issues else "None"
        suggestions_text = "\n".join(f"- {s}" for s in suggestions) if suggestions else "None"

        return f"""You are revising a NSW Selective Schools exam question that failed quality checks.

## Original Question
{question.get('question', 'No question')}

## Original Choices
{json.dumps(question.get('choices', []), indent=2)}

## Issues Found
{issues_text}

## Suggestions for Improvement
{suggestions_text}

## Your Task
Create a REVISED question that addresses ALL issues while maintaining:
- The same concept being tested: {blueprint.get('concept_name', 'Unknown')}
- The same target difficulty: {blueprint.get('difficulty_target', 3)}/3
- Clear, unambiguous structure
- AUSTRALIAN ENGLISH spelling (colour, favourite, centre, metre, travelled, organisation)
- Australian locations only (Sydney, Melbourne, Brisbane, Perth, Adelaide, etc.)
- Australian context (AUD currency, Australian schools, Australian seasons)

Output the revised question in JSON format:

{{
    "setup_elements": [...],
    "question_stem_structure": "...",
    "constraints": [...],
    "correct_answer_reasoning": "...",
    "solution_steps": [...],
    "requires_image": true/false,
    "image_spec": "...",
    "question_text": "The revised question text",
    "choices": [
        {{"id": "1", "text": "Correct answer"}},
        {{"id": "2", "text": "Wrong answer", "misconception": "..."}},
        {{"id": "3", "text": "Wrong answer", "misconception": "..."}},
        {{"id": "4", "text": "Wrong answer", "misconception": "..."}}
    ],
    "explanation": "...",
    "tags": [...]
}}

Output ONLY the JSON object."""

    def _parse_blueprint(
        self,
        data: dict,
        concept_data: dict,
        target_difficulty: int,
        topic: str = "thinking_skills",
    ) -> QuestionBlueprint:
        """Parse generated data into a QuestionBlueprint."""
        # Determine number of distractors based on topic
        # Math has 5 choices (1 correct + 4 distractors)
        # Thinking skills has 4 choices (1 correct + 3 distractors)
        num_distractors = 4 if topic == "math" else 3
        distractor_end = num_distractors + 1

        # Parse distractors from choices
        distractors = []
        for c in data.get("choices", [])[1:distractor_end]:  # Skip first (correct) answer
            distractors.append(DistractorSpec(
                id=c.get("id", str(len(distractors) + 2)),
                misconception=c.get("misconception", "Plausible but incorrect"),
                error_type="conceptual",
                text_hint=c.get("text"),
            ))

        # Ensure we have the right number of distractors
        while len(distractors) < num_distractors:
            distractors.append(DistractorSpec(
                id=str(len(distractors) + 2),
                misconception="Plausible but incorrect",
                error_type="conceptual",
            ))

        # Parse solution steps
        solution_steps = []
        for s in data.get("solution_steps", []):
            solution_steps.append(SolutionStep(
                step_number=s.get("step_number", len(solution_steps) + 1),
                description=s.get("description", ""),
                reasoning=s.get("reasoning", ""),
            ))

        subtopic_id = concept_data.get("subtopic_id")
        if isinstance(subtopic_id, str):
            try:
                subtopic_id = UUID(subtopic_id)
            except (ValueError, TypeError):
                subtopic_id = UUID("00000000-0000-0000-0000-000000000000")

        # Thinking Skills and Math are always MCQ
        subtopic_name = concept_data.get("subtopic_name", "Unknown")
        q_type = QuestionType.MCQ

        # Get the correct topic UUID
        topic_uuid_key = "mathematics" if topic == "math" else "thinking_skills"
        topic_uuid_str = config.topic_uuids.get(topic_uuid_key, config.topic_uuids.get("thinking_skills"))

        return QuestionBlueprint(
            concept_id=concept_data.get("id", "unknown"),
            concept_name=concept_data.get("name", "Unknown"),
            subtopic_id=subtopic_id or UUID("00000000-0000-0000-0000-000000000000"),
            subtopic_name=subtopic_name,
            topic_id=UUID(topic_uuid_str),
            question_type=q_type,
            target_skill=TargetSkill.APPLICATION,
            difficulty_target=target_difficulty,
            setup_elements=data.get("setup_elements", []),
            question_stem_structure=data.get("question_stem_structure", ""),
            constraints=data.get("constraints", []),
            correct_answer_value=data.get("choices", [{}])[0].get("text") if data.get("choices") else None,
            correct_answer_reasoning=data.get("correct_answer_reasoning", ""),
            distractors=distractors,
            solution_steps=solution_steps,
            requires_image=data.get("requires_image", False),
            image_spec=data.get("image_spec"),
            tags=data.get("tags", ["Thinking Skills"]),
        )

    def _parse_question(self, data: dict, blueprint: QuestionBlueprint, topic: str = "thinking_skills") -> Question:
        """Parse generated data into a Question model.

        Note: Thinking Skills and Math are always multiple-choice.
        Math has 5 choices, Thinking Skills has 4 choices.
        """
        choices = []
        # Math has 5 choices, Thinking Skills has 4
        num_choices = 5 if topic == "math" else 4

        # Standard MCQ: is_correct bool, first choice is correct
        for i, c in enumerate(data.get("choices", [])):
            choices.append(Choice(
                id=c.get("id", str(i + 1)),
                text=c.get("text", ""),
                is_correct=(i == 0),  # First choice is correct
            ))

        # Ensure we have the right number of choices
        while len(choices) < num_choices:
            choices.append(Choice(
                id=str(len(choices) + 1),
                text=f"Option {len(choices) + 1}",
                is_correct=False,
            ))

        # Get content field for NSW exam format (Deduction/Inference have premise + character content)
        content = data.get("content")

        return Question(
            content=content,
            question=data.get("question_text", ""),
            choices=choices,
            type=QuestionTypeEnum.MULTIPLE_CHOICE.value,
            explanation=data.get("explanation", "No explanation provided."),
            difficulty=str(blueprint.difficulty_target),
            topic_id=blueprint.topic_id,
            subtopic_id=blueprint.subtopic_id,
            subtopic_name=blueprint.subtopic_name,
            requires_image=blueprint.requires_image,
            image_description=blueprint.image_spec,
            tags=blueprint.tags,
        )


async def main():
    """Run the Question Generator Agent."""
    agent = QuestionGeneratorAgent()
    print(f"Starting Question Generator Agent on port {config.ports.question_generator}...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
