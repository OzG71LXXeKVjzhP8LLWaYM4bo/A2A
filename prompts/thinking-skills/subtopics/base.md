You are an expert educational content creator for NSW Selective Schools Thinking Skills exams.

Generate exactly {{COUNT}} unique {{DISPLAY_NAME}} questions.

## Subtopic: {{DISPLAY_NAME}}
{{DESCRIPTION}}

{{SUBTOPIC_INSTRUCTIONS}}

## CRITICAL: AI-ESTIMATED DIFFICULTY
You must estimate the appropriate difficulty level (1, 2, or 3) for EACH question based on cognitive complexity:

### Difficulty 1 (Easy) - Target: 60-70% success rate
- Single-step reasoning, obvious patterns
- Clear relationships, 1-2 pieces of information
- Pattern is immediately recognizable

### Difficulty 2 (Medium) - Target: 40-50% success rate
- 2-3 step reasoning required
- Compound patterns or hidden relationships
- 3-4 pieces of information to hold

### Difficulty 3 (Hard) - Target: 20-30% success rate
- 4+ step reasoning, complex multi-concept
- Requires insight or creative thinking
- 4-5 pieces of information, solution not obvious

**Distribute difficulty naturally based on question complexity:**
- Approximately 30% should be Easy (difficulty: "1")
- Approximately 40% should be Medium (difficulty: "2")
- Approximately 30% should be Hard (difficulty: "3")

## Requirements:
- 4 answer options (1-4), exactly one correct
- Detailed step-by-step explanation (concise, max 100 words)
- Estimate difficulty for EACH question individually (do NOT use same difficulty for all)

{{IMAGE_SECTION}}

## Database Subtopic (use this exact name for all questions):
- {{DB_SUBTOPIC_NAME}}

{{CUSTOM_INSTRUCTIONS}}

## Output Format (JSON array):
[
  {
    "content": "Setup/pattern/sequence here, or null if none needed",
    "question": "The actual question being asked?",
    "choices": [{"id": "1", "text": "...", "is_correct": false}, {"id": "2", "text": "...", "is_correct": true}, {"id": "3", "text": "...", "is_correct": false}, {"id": "4", "text": "...", "is_correct": false}],
    "explanation": "Step-by-step with <strong>HTML</strong>",
    "difficulty": "1|2|3",
    "subtopic_name": "{{DB_SUBTOPIC_NAME}}",
    "requires_image": false,
    "image_description": null,
    "tags": ["Thinking Skills", "{{DISPLAY_NAME}}"]
  }
]

CRITICAL RULES (MUST FOLLOW):
1. Return ONLY the JSON array, starting with [ and ending with ]
2. Generate exactly {{COUNT}} questions
3. Difficulty MUST be a string: "1", "2", or "3"
4. Each question should have a DIFFERENT difficulty based on its actual complexity
5. NEVER use literal \\n (backslash-n) in ANY field - no newline escape sequences allowed. Use spaces or <br> tags instead
6. EXPLANATIONS MUST BE CONCISE (MAX 100 WORDS): Do NOT include any thinking, reasoning process, internal deliberation, or phrases like "Let me...", "I need to...", "First, I'll...", "To solve this...". Just state the steps directly
7. Use subtopic_name: "{{DB_SUBTOPIC_NAME}}" for ALL questions
