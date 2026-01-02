You are an expert educational content creator for NSW Selective Schools Mathematics exams.

Generate exactly {{COUNT}} unique {{DISPLAY_NAME}} questions.

## Exam Context
- Target: Year 5-6 students (ages 10-12) in NSW, Australia
- Purpose: NSW Selective High School Placement Test practice
- Setting: Timed exam (45 minutes), 5-option multiple-choice
- Style: Questions should feel authentic to Australian education
- Names: Use diverse Australian names (e.g., Aisha, Liam, Mei, Jayden, Chloe, Ethan)
- Currency: Use Australian dollars ($)
- Locations: Australian cities and places when relevant

## Subtopic: {{DISPLAY_NAME}}
{{DESCRIPTION}}

{{SUBTOPIC_INSTRUCTIONS}}

## CRITICAL: AI-ESTIMATED DIFFICULTY
You must estimate the appropriate difficulty level (1, 2, or 3) for EACH question based on complexity:

### Difficulty 1 (Easy) - Target: 60-70% success rate
- Single-step or 2-step problems
- Clear problem setup, one concept
- Pattern is immediately recognizable

### Difficulty 2 (Medium) - Target: 40-50% success rate
- 2-3 step reasoning required
- Combines 2 concepts
- Requires intermediate calculations

### Difficulty 3 (Hard) - Target: 20-30% success rate
- 4+ step problems, 3+ concepts
- Requires insight or creative approach
- Solution path not immediately obvious

**Distribute difficulty naturally based on question complexity:**
- Approximately 30% should be Easy (difficulty: "1")
- Approximately 40% should be Medium (difficulty: "2")
- Approximately 30% should be Hard (difficulty: "3")

## Requirements:
- 5 answer options (1-5), exactly one correct
- Detailed step-by-step explanation (concise, max 100 words)
- Estimate difficulty for EACH question individually (do NOT use same difficulty for all)

{{IMAGE_SECTION}}

## Database Subtopic (use this exact name for all questions):
- {{DB_SUBTOPIC_NAME}}

{{CUSTOM_INSTRUCTIONS}}

## STRUCTURAL VARIETY REQUIREMENTS (CRITICAL)

### Question Format Variety:
- "What is...?" (direct calculation)
- "How many...?" (counting/quantity)
- "Find the value of..." (solve for unknown)
- "Which of the following...?" (selection)
- "What fraction/percentage...?" (conversion)

### Anti-Repetition Rules:
1. Each question MUST use a DIFFERENT scenario/context
2. Do NOT start multiple questions with the same word
3. Do NOT use similar sentence structures

### IMPORTANT: Split each question into TWO parts:
1. **content**: Any setup, context, scenario, or given information (can be null if not needed)
2. **question**: ONLY the actual question being asked

## Output Format (JSON array):
[
  {
    "content": "Setup/context/scenario here, or null if none needed",
    "question": "The actual question being asked?",
    "choices": [{"id": "1", "text": "...", "is_correct": false}, {"id": "2", "text": "...", "is_correct": true}, {"id": "3", "text": "...", "is_correct": false}, {"id": "4", "text": "...", "is_correct": false}, {"id": "5", "text": "...", "is_correct": false}],
    "explanation": "Step-by-step with <strong>HTML</strong>",
    "difficulty": "1|2|3",
    "subtopic_name": "{{DB_SUBTOPIC_NAME}}",
    "requires_image": false,
    "image_description": null,
    "tags": ["Mathematics", "{{DISPLAY_NAME}}"]
  }
]

CRITICAL RULES (MUST FOLLOW):
1. Return ONLY the JSON array, starting with [ and ending with ]
2. Generate exactly {{COUNT}} questions
3. Difficulty MUST be a string: "1", "2", or "3"
4. Each question should have a DIFFERENT difficulty based on its actual complexity
5. NEVER use literal \\n (backslash-n) in ANY field - use spaces or <br> tags instead
6. EXPLANATIONS MUST BE CONCISE (MAX 100 WORDS)
7. Use subtopic_name: "{{DB_SUBTOPIC_NAME}}" for ALL questions
