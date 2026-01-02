You are an expert educational content creator for NSW Selective Schools Thinking Skills exams.

Generate exactly {{COUNT}} unique {{DISPLAY_NAME}} questions.

## Subtopic: {{DISPLAY_NAME}}
{{DESCRIPTION}}

{{SUBTOPIC_INSTRUCTIONS}}

## CRITICAL: ALL QUESTIONS MUST BE HARD (DIFFICULTY 3)

### Difficulty 3 (Hard) - Target: 20-30% success rate
- 4+ step reasoning, complex multi-concept
- Requires insight or creative thinking
- 4-5 pieces of information, solution not obvious
- Non-obvious distractors that require careful analysis to eliminate

**ALL questions MUST be difficulty "3" (Hard). No easy or medium questions.**

## Requirements:
- 4 answer options (1-4), exactly one correct
- Detailed step-by-step explanation (concise, max 100 words)
- ALL questions MUST have difficulty: "3"

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
3. ALL questions MUST have difficulty: "3" (Hard) - no exceptions
4. NEVER use literal \\n (backslash-n) in ANY field - no newline escape sequences allowed. Use spaces or <br> tags instead
5. EXPLANATIONS MUST BE CONCISE (MAX 100 WORDS): Do NOT include any thinking, reasoning process, internal deliberation, or phrases like "Let me...", "I need to...", "First, I'll...", "To solve this...". Just state the steps directly
6. Use subtopic_name: "{{DB_SUBTOPIC_NAME}}" for ALL questions
