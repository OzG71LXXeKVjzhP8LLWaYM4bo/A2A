---
name: question-formats
description: Comprehensive documentation of all JSON formats for questions, answers, and marking criteria in PrepSelective. Reference this when creating, editing, or validating question data.
allowed-tools: Read
---

# PrepSelective Question Format Reference

Complete, self-contained documentation for all JSON schemas used in the PrepSelective question system. This document covers question formats, answer formats, marking criteria, TypeScript types, database schemas, validation rules, and implementation patterns.

---

## Table of Contents

1. [Question Types Overview](#question-types-overview)
2. [TypeScript Type Definitions](#typescript-type-definitions)
3. [Question Formats by Type](#question-formats-by-type)
4. [Answer Storage Formats](#answer-storage-formats)
5. [Marking Criteria Schema](#marking-criteria-schema)
6. [Database Schema Reference](#database-schema-reference)
7. [Validation Rules](#validation-rules)
8. [Implementation Patterns](#implementation-patterns)
9. [Analytics Fields](#analytics-fields)
10. [Email Preferences Schema](#email-preferences-schema)

---

## Question Types Overview

| Type | Description | Uses Choices | Uses Marking Criteria | Supports Partial Credit |
|------|-------------|--------------|----------------------|------------------------|
| `multiple-choice` | Standard A/B/C/D questions | Yes | No | No |
| `multiple-choice-with-images` | MCQ with image options | Yes | No | No |
| `drag-and-drop` | Order items correctly | Yes | No | No |
| `multi-subquestion` | Multiple questions per passage | Yes | No | Yes |
| `cloze` | Fill-in-the-blank dropdown | Yes | No | Yes |
| `writing` | Free-text response | No (null) | Yes | Yes (rubric-based) |

---

## TypeScript Type Definitions

### Core Types

```typescript
/**
 * All supported question types in the system
 */
export type QuestionType =
  | 'multiple-choice'
  | 'drag-and-drop'
  | 'writing'
  | 'multiple-choice-with-images'
  | 'multi-subquestion'
  | 'cloze';

/**
 * Universal Choice interface - fields used depend on question type
 */
export interface Choice {
  /** String identifier, typically "1", "2", "3", "4" */
  id: string;

  /** Display text for the choice */
  text: string;

  /**
   * For MCQ: boolean (true = correct answer)
   * For cloze: number 0-3 (index of correct option)
   */
  is_correct?: boolean | number;

  /** For multi-subquestion: the correct extract letter (A, B, C, etc.) */
  correct?: string;

  /** For drag-and-drop: position in correct order (1-indexed), null = distractor */
  correct_position?: number | null;

  /** For multiple-choice-with-images: URL to the image */
  image?: string;

  /** For cloze: array of exactly 4 option strings for this blank */
  options?: string[];
}

/**
 * Marking criterion for writing/essay questions
 */
export interface MarkingCriterion {
  /** Unique identifier for the criterion */
  id: string;

  /** Display name (e.g., "Grammar", "Content", "Structure") */
  name: string;

  /** Maximum points available for this criterion */
  max_marks: number;

  /** Description of what is being assessed */
  description: string;
}

/**
 * Complete question data structure
 */
export interface QuestionFormData {
  /** Main question text, passage, or prompt */
  content: string;

  /** Short display text for the question */
  question: string;

  /** Explanation shown after answering */
  explanation: string;

  /** Question type identifier */
  type: QuestionType;

  /** Difficulty rating (1-5 scale) */
  difficulty: number;

  /** UUID of the parent topic */
  topic_id: string;

  /** Array of UUIDs for subtopics */
  subtopic_ids: string[];

  /** Choices array - structure varies by type */
  choices: Choice[];

  /** Optional string tags for categorization */
  tags: string[];

  /** Whether question is visible/active */
  showup: boolean;

  /** UUID of associated exam (if any) */
  exam_id: string;

  /** Order position within exam */
  question_order: number;

  /** Marking criteria for writing questions */
  marking_criteria: MarkingCriterion[];

  /** For drag-and-drop: number of slots to fill */
  max_positions?: number;

  /** Array of UUIDs referencing extracts table */
  extract_id?: string[] | null;
}

/**
 * Image upload info (frontend only)
 */
export interface ImageInfo {
  fileId: string;
  file: File;
  finalWidth: number;
  finalHeight: number;
}
```

### Answer Types

```typescript
/**
 * Base answer structure - all answers have a type field
 */
interface BaseAnswer {
  type: string;
}

/**
 * Multiple choice answer
 */
interface MultipleChoiceAnswer extends BaseAnswer {
  type: 'multiple_choice';
  /** Choice ID that was selected */
  selected: string;
  /** Optional confidence level */
  confidence?: 'low' | 'medium' | 'high';
}

/**
 * Multiple choice with images answer
 */
interface MultipleChoiceWithImagesAnswer extends BaseAnswer {
  type: 'multiple_choice_with_images';
  selected: string;
  confidence?: 'low' | 'medium' | 'high';
}

/**
 * Drag and drop answer
 */
interface DragAndDropAnswer extends BaseAnswer {
  type: 'drag_and_drop';
  /** Array of choice IDs in the order user arranged them */
  order: string[];
  confidence?: 'low' | 'medium' | 'high';
}

/**
 * Multi-subquestion answer
 */
interface MultiSubquestionAnswer extends BaseAnswer {
  type: 'multi_subquestion';
  /** Maps subquestion ID to selected extract letter */
  multiSubAnswers: Record<string, string>;
}

/**
 * Cloze/fill-in-the-blank answer
 */
interface ClozeAnswer extends BaseAnswer {
  type: 'cloze';
  /** Maps blank ID to selected option index (0-3) */
  blanks: Record<string, number>;
}

/**
 * Writing/essay answer
 */
interface WritingAnswer extends BaseAnswer {
  type: 'writing';
  /** The student's written response */
  writingResponse: string;
  /** Word count of the response */
  word_count?: number;
}

/**
 * Union type for all answer formats
 */
type AnswerData =
  | MultipleChoiceAnswer
  | MultipleChoiceWithImagesAnswer
  | DragAndDropAnswer
  | MultiSubquestionAnswer
  | ClozeAnswer
  | WritingAnswer;
```

### Marking Score Types

```typescript
/**
 * Individual criterion score from marking
 */
interface CriterionScore {
  id: string;
  name: string;
  max_marks: number;
  description: string;
  /** Actual score awarded */
  score: number;
  /** Marker's comment for this criterion */
  comment?: string;
}

/**
 * Complete marking result stored in attempt_answers.marking_criteria_score
 */
interface MarkingCriteriaScore {
  criteria: CriterionScore[];
  /** Overall feedback comment */
  overall_comment?: string;
}
```

### Report Types

```typescript
/**
 * Detailed question result for reports
 */
interface DetailedQuestionResult {
  order: number;
  is_correct: boolean;
  difficulty: string;
  category: string;
  time_spent: number;
  question_type: QuestionType;
}

/**
 * Topic performance summary
 */
interface TopicPerformance {
  topic_name: string;
  correct: number;
  total: number;
  percentage: number;
}

/**
 * Cache structure for test state
 */
interface TestCacheData {
  examId: string;
  attemptId: string;
  answers: Record<string, AnswerData>;
  timeSpent: Record<string, number>;
  flaggedQuestions: string[];
  lastSaved: number;
}
```

---

## Question Formats by Type

### 1. Multiple Choice (`multiple-choice`)

Standard single-answer multiple choice question.

**`choices` field structure:**
```json
[
  {
    "id": "1",
    "text": "Sydney",
    "is_correct": true
  },
  {
    "id": "2",
    "text": "Melbourne",
    "is_correct": false
  },
  {
    "id": "3",
    "text": "Brisbane",
    "is_correct": false
  },
  {
    "id": "4",
    "text": "Perth",
    "is_correct": false
  }
]
```

**Complete question example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "content": "Which city was the first European settlement in Australia?",
  "question": "First European Settlement",
  "explanation": "Sydney was founded in 1788 as a British penal colony, making it the first European settlement in Australia.",
  "type": "multiple-choice",
  "difficulty": 2,
  "topic_id": "660e8400-e29b-41d4-a716-446655440001",
  "subtopic_ids": ["770e8400-e29b-41d4-a716-446655440002"],
  "choices": [
    { "id": "1", "text": "Sydney", "is_correct": true },
    { "id": "2", "text": "Melbourne", "is_correct": false },
    { "id": "3", "text": "Brisbane", "is_correct": false },
    { "id": "4", "text": "Perth", "is_correct": false }
  ],
  "tags": ["history", "australia"],
  "showup": true,
  "marking_criteria": [],
  "extract_id": null
}
```

**Rules:**
- Exactly ONE choice must have `is_correct: true`
- All other choices must have `is_correct: false`
- `id` values are strings (typically "1", "2", "3", "4")
- `is_correct` is boolean type
- Minimum 2 choices, maximum typically 4-5

---

### 2. Multiple Choice with Images (`multiple-choice-with-images`)

Multiple choice where each option includes an image.

**`choices` field structure:**
```json
[
  {
    "id": "1",
    "text": "Kangaroo",
    "is_correct": true,
    "image": "https://cdn.prepselective.com/images/kangaroo.jpg"
  },
  {
    "id": "2",
    "text": "Koala",
    "is_correct": false,
    "image": "https://cdn.prepselective.com/images/koala.jpg"
  },
  {
    "id": "3",
    "text": "Emu",
    "is_correct": false,
    "image": "https://cdn.prepselective.com/images/emu.jpg"
  },
  {
    "id": "4",
    "text": "Platypus",
    "is_correct": false,
    "image": "https://cdn.prepselective.com/images/platypus.jpg"
  }
]
```

**Complete question example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440010",
  "content": "Which animal is shown on the Australian coat of arms?",
  "question": "Coat of Arms Animal",
  "explanation": "The kangaroo appears on the Australian coat of arms along with the emu.",
  "type": "multiple-choice-with-images",
  "difficulty": 1,
  "topic_id": "660e8400-e29b-41d4-a716-446655440001",
  "subtopic_ids": [],
  "choices": [
    { "id": "1", "text": "Kangaroo", "is_correct": true, "image": "https://cdn.example.com/kangaroo.jpg" },
    { "id": "2", "text": "Koala", "is_correct": false, "image": "https://cdn.example.com/koala.jpg" },
    { "id": "3", "text": "Emu", "is_correct": false, "image": "https://cdn.example.com/emu.jpg" },
    { "id": "4", "text": "Platypus", "is_correct": false, "image": "https://cdn.example.com/platypus.jpg" }
  ],
  "tags": ["visual", "symbols"],
  "showup": true,
  "marking_criteria": [],
  "extract_id": null
}
```

**Rules:**
- Same rules as multiple-choice
- MUST include `image` field with valid URL for each choice
- Images should be hosted on CDN/cloud storage
- Supports jpg, png, gif, webp formats

---

### 3. Drag and Drop (`drag-and-drop`)

User arranges items in correct order.

**`choices` field structure:**
```json
{
  "choices": [
    {
      "id": "1",
      "text": "Wash your hands",
      "correct_position": 1
    },
    {
      "id": "2",
      "text": "Dry your hands",
      "correct_position": 3
    },
    {
      "id": "3",
      "text": "Apply soap",
      "correct_position": 2
    },
    {
      "id": "4",
      "text": "Skip washing (wrong)",
      "correct_position": null
    }
  ],
  "max_positions": 3
}
```

**Complete question example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440020",
  "content": "Arrange the steps for proper hand washing in the correct order.",
  "question": "Hand Washing Steps",
  "explanation": "The correct order is: 1) Wet hands, 2) Apply soap, 3) Scrub, 4) Rinse, 5) Dry.",
  "type": "drag-and-drop",
  "difficulty": 2,
  "topic_id": "660e8400-e29b-41d4-a716-446655440001",
  "subtopic_ids": [],
  "choices": [
    { "id": "1", "text": "Wet your hands", "correct_position": 1 },
    { "id": "2", "text": "Apply soap", "correct_position": 2 },
    { "id": "3", "text": "Scrub for 20 seconds", "correct_position": 3 },
    { "id": "4", "text": "Rinse thoroughly", "correct_position": 4 },
    { "id": "5", "text": "Dry with clean towel", "correct_position": 5 },
    { "id": "6", "text": "Use cold water only (wrong)", "correct_position": null }
  ],
  "max_positions": 5,
  "tags": ["ordering", "health"],
  "showup": true,
  "marking_criteria": [],
  "extract_id": null
}
```

**Rules:**
- Uses `correct_position` field (NOT `is_correct`)
- `correct_position` is 1-indexed (starts at 1, not 0)
- `correct_position: null` marks a distractor/wrong option
- `max_positions` must equal the count of non-null positions
- Positions must be sequential (1, 2, 3... no gaps)
- The `is_correct` field is IGNORED for this type

---

### 4. Multi-Subquestion (`multi-subquestion`)

Multiple questions that reference text passages (extracts).

**`choices` field structure (direct array, not wrapped):**
```json
[
  {
    "id": "1",
    "text": "What is the main idea of the text?",
    "correct": "A"
  },
  {
    "id": "2",
    "text": "Which statement best supports the author's argument?",
    "correct": "B"
  },
  {
    "id": "3",
    "text": "What can you infer about the character's motivation?",
    "correct": "A"
  },
  {
    "id": "4",
    "text": "Which text provides evidence of the theme?",
    "correct": "C"
  }
]
```

**Complete question example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440030",
  "content": "Read the three texts and answer the following questions by selecting the correct text (A, B, or C).",
  "question": "Reading Comprehension",
  "explanation": "Text A discusses the main theme, Text B provides supporting evidence, and Text C shows character development.",
  "type": "multi-subquestion",
  "difficulty": 4,
  "topic_id": "660e8400-e29b-41d4-a716-446655440001",
  "subtopic_ids": [],
  "choices": [
    { "id": "1", "text": "What is the main idea?", "correct": "A" },
    { "id": "2", "text": "Which supports the argument?", "correct": "B" },
    { "id": "3", "text": "What is the character's motivation?", "correct": "A" },
    { "id": "4", "text": "Which shows the theme?", "correct": "C" }
  ],
  "tags": ["reading", "comprehension"],
  "showup": true,
  "marking_criteria": [],
  "extract_id": [
    "880e8400-e29b-41d4-a716-446655440001",
    "880e8400-e29b-41d4-a716-446655440002",
    "880e8400-e29b-41d4-a716-446655440003"
  ]
}
```

**Rules:**
- Each choice is a subquestion with `id`, `text`, and `correct` fields
- `correct` = letter (A, B, C...) corresponding to extract
- `extract_id` array must contain UUIDs from the `extracts` table
- Extract letters map alphabetically to `extract_id` array:
  - A = extract_id[0]
  - B = extract_id[1]
  - C = extract_id[2]
  - etc.
- Supports partial credit (each subquestion scored independently)
- Score = (correct subquestions / total subquestions)

---

### 5. Cloze/Fill-in-the-Blank (`cloze`)

Passage with dropdown blanks to fill in.

**`content` field (passage with placeholders):**
```
The {{1}} is the largest ocean on Earth, covering approximately {{2}} percent of the planet's surface. It is deeper than the {{3}} Ocean.
```

**`choices` field structure:**
```json
[
  {
    "id": "1",
    "text": "",
    "options": ["Pacific Ocean", "Atlantic Ocean", "Indian Ocean", "Arctic Ocean"],
    "is_correct": 0
  },
  {
    "id": "2",
    "text": "",
    "options": ["30", "46", "63", "71"],
    "is_correct": 1
  },
  {
    "id": "3",
    "text": "",
    "options": ["Atlantic", "Indian", "Arctic", "Southern"],
    "is_correct": 0
  }
]
```

**Complete question example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440040",
  "content": "The {{1}} is the largest ocean on Earth, covering approximately {{2}} percent of the planet's surface. It contains about {{3}} percent of Earth's water.",
  "question": "Ocean Facts",
  "explanation": "The Pacific Ocean is the largest, covering about 46% of Earth's surface and containing about 50% of Earth's water.",
  "type": "cloze",
  "difficulty": 3,
  "topic_id": "660e8400-e29b-41d4-a716-446655440001",
  "subtopic_ids": [],
  "choices": [
    { "id": "1", "text": "", "options": ["Pacific Ocean", "Atlantic Ocean", "Indian Ocean", "Arctic Ocean"], "is_correct": 0 },
    { "id": "2", "text": "", "options": ["30", "46", "63", "71"], "is_correct": 1 },
    { "id": "3", "text": "", "options": ["30", "50", "70", "90"], "is_correct": 1 }
  ],
  "tags": ["geography", "oceans"],
  "showup": true,
  "marking_criteria": [],
  "extract_id": null
}
```

**Rules:**
- `{{N}}` placeholders in content must match choice `id` values
- Each choice must have `options` array with EXACTLY 4 strings
- `is_correct` is a NUMBER (0, 1, 2, or 3) = index of correct option
- `text` field is empty string "" (not used, kept for type consistency)
- Options are RANDOMIZED on display
- Answer is stored using ORIGINAL index (pre-randomization)
- Supports partial credit:
  - Score = (correct blanks / total blanks)
  - Example: 2/3 blanks correct = 0.667 score

---

### 6. Writing/Essay (`writing`)

Free-text response with rubric-based marking.

**`choices` field:** `null`

**`marking_criteria` field structure:**
```json
[
  {
    "id": "grammar",
    "name": "Grammar & Spelling",
    "max_marks": 20,
    "description": "Correct grammar, punctuation, and spelling throughout the response."
  },
  {
    "id": "content",
    "name": "Content & Ideas",
    "max_marks": 40,
    "description": "Relevance, depth, and quality of ideas presented."
  },
  {
    "id": "structure",
    "name": "Structure & Organization",
    "max_marks": 25,
    "description": "Logical flow, paragraphing, and coherent organization."
  },
  {
    "id": "vocabulary",
    "name": "Vocabulary & Expression",
    "max_marks": 15,
    "description": "Range and appropriateness of vocabulary used."
  }
]
```

**Complete question example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440050",
  "content": "Write a persuasive essay (200-300 words) arguing for or against school uniforms. Include at least three supporting arguments.",
  "question": "Persuasive Essay: School Uniforms",
  "explanation": "A strong response should include a clear thesis, multiple supporting arguments with evidence, and a conclusion.",
  "type": "writing",
  "difficulty": 4,
  "topic_id": "660e8400-e29b-41d4-a716-446655440001",
  "subtopic_ids": [],
  "choices": null,
  "tags": ["essay", "persuasive"],
  "showup": true,
  "marking_criteria": [
    { "id": "thesis", "name": "Thesis & Argument", "max_marks": 30, "description": "Clear thesis with well-developed arguments." },
    { "id": "evidence", "name": "Evidence & Support", "max_marks": 30, "description": "Quality and relevance of supporting evidence." },
    { "id": "structure", "name": "Structure", "max_marks": 20, "description": "Logical organization with intro, body, conclusion." },
    { "id": "language", "name": "Language Use", "max_marks": 20, "description": "Grammar, spelling, and vocabulary." }
  ],
  "extract_id": null
}
```

**Rules:**
- `choices` MUST be `null`
- `marking_criteria` should have at least one criterion
- Each criterion needs: `id`, `name`, `max_marks`, `description`
- Total marks = sum of all `max_marks` values
- Requires manual marking by teacher
- `is_marked` flag tracks marking status

---

## Answer Storage Formats

Answers are stored in `attempt_answers.answer` as JSONB.

### Multiple Choice Answer
```json
{
  "type": "multiple_choice",
  "selected": "1",
  "confidence": "high"
}
```
- `selected`: The choice ID that was selected
- `confidence`: Optional ("low", "medium", "high")

### Multiple Choice with Images Answer
```json
{
  "type": "multiple_choice_with_images",
  "selected": "2",
  "confidence": "medium"
}
```
- Same structure as multiple choice

### Drag and Drop Answer
```json
{
  "type": "drag_and_drop",
  "order": ["2", "1", "3"],
  "confidence": "low"
}
```
- `order`: Array of choice IDs in the order user arranged them
- Length should match `max_positions`

### Multi-Subquestion Answer
```json
{
  "type": "multi_subquestion",
  "multiSubAnswers": {
    "1": "A",
    "2": "B",
    "3": "A",
    "4": "C"
  }
}
```
- `multiSubAnswers`: Object mapping subquestion ID to selected extract letter
- Keys match the choice `id` values
- Values are letters (A, B, C, etc.)

### Cloze Answer
```json
{
  "type": "cloze",
  "blanks": {
    "1": 0,
    "2": 1,
    "3": 1
  }
}
```
- `blanks`: Object mapping blank ID to selected option INDEX (0-3)
- Uses ORIGINAL index, not the randomized display index
- Keys match the choice `id` values (which match `{{N}}` placeholders)

### Writing Answer
```json
{
  "type": "writing",
  "writingResponse": "School uniforms have been a topic of debate for many years. I believe that school uniforms should be mandatory in all schools for several important reasons...",
  "word_count": 245
}
```
- `writingResponse`: The full text of the student's response
- `word_count`: Optional word count

---

## Marking Criteria Schema

### Question Marking Criteria (`questionbank.marking_criteria`)

Defines the rubric for marking writing questions:

```json
[
  {
    "id": "criterion_1",
    "name": "Content & Ideas",
    "max_marks": 40,
    "description": "Quality, relevance, and depth of ideas presented"
  },
  {
    "id": "criterion_2",
    "name": "Structure",
    "max_marks": 30,
    "description": "Organization, paragraphing, and logical flow"
  },
  {
    "id": "criterion_3",
    "name": "Language",
    "max_marks": 30,
    "description": "Grammar, spelling, vocabulary, and expression"
  }
]
```

### Marking Score Result (`attempt_answers.marking_criteria_score`)

Stores the teacher's marking:

```json
{
  "criteria": [
    {
      "id": "criterion_1",
      "name": "Content & Ideas",
      "max_marks": 40,
      "description": "Quality, relevance, and depth of ideas presented",
      "score": 35,
      "comment": "Good ideas, well-developed arguments"
    },
    {
      "id": "criterion_2",
      "name": "Structure",
      "max_marks": 30,
      "description": "Organization, paragraphing, and logical flow",
      "score": 25,
      "comment": "Clear structure, but conclusion could be stronger"
    },
    {
      "id": "criterion_3",
      "name": "Language",
      "max_marks": 30,
      "description": "Grammar, spelling, vocabulary, and expression",
      "score": 28,
      "comment": "Minor spelling errors, good vocabulary range"
    }
  ],
  "overall_comment": "A strong essay with clear arguments. Focus on strengthening your conclusion in future work."
}
```

**Scoring Calculation:**
- `total_score` = sum(criteria[].score) = 35 + 25 + 28 = 88
- `max_total` = sum(criteria[].max_marks) = 40 + 30 + 30 = 100
- `percentage` = (88 / 100) * 100 = 88%

---

## Database Schema Reference

### `questionbank` Table

```sql
CREATE TABLE questionbank (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,                    -- Main question text/passage
  question TEXT,                            -- Short display question
  choices JSONB,                            -- Choices array (varies by type)
  type TEXT NOT NULL,                       -- Question type identifier
  difficulty INTEGER DEFAULT 3,             -- 1-5 difficulty scale
  topic_id UUID REFERENCES topics(id),      -- Parent topic
  subtopic_ids UUID[] DEFAULT '{}',         -- Subtopic references
  extract_id UUID[],                        -- Extract references
  marking_criteria JSONB,                   -- For writing questions
  explanation TEXT,                         -- Answer explanation
  tags TEXT[],                              -- Optional categorization tags
  showup BOOLEAN DEFAULT true,              -- Visibility flag
  most_common_choice JSONB,                 -- Analytics: most selected answer
  percent_correct FLOAT,                    -- Analytics: success rate
  total_attempts INTEGER DEFAULT 0,         -- Analytics: attempt count
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `attempt_answers` Table

```sql
CREATE TABLE attempt_answers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  attempt_id UUID REFERENCES attempts(id) ON DELETE CASCADE,
  question_id UUID REFERENCES questionbank(id),
  answer JSONB,                             -- User's answer (varies by type)
  is_correct BOOLEAN,                       -- Overall correctness
  is_marked BOOLEAN DEFAULT false,          -- Manual marking status
  marking_criteria_score JSONB,             -- Detailed marking scores
  time_spent INTEGER DEFAULT 0,             -- Seconds spent on question
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `attempts` Table

```sql
CREATE TABLE attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  exam_id UUID REFERENCES exams(id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  total_correct INTEGER DEFAULT 0,
  total_marks FLOAT DEFAULT 0,
  total_possible FLOAT,
  time_taken INTEGER,                       -- Total seconds
  is_submitted BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `extracts` Table

```sql
CREATE TABLE extracts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  content TEXT NOT NULL,                    -- The passage text
  source TEXT,                              -- Attribution/source info
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `topics` Table

```sql
CREATE TABLE topics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `subtopics` Table

```sql
CREATE TABLE subtopics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `profiles` Table (relevant fields)

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  subscription_type TEXT DEFAULT 'free',
  subscription_status TEXT,
  is_admin BOOLEAN DEFAULT false,
  is_teacher BOOLEAN DEFAULT false,
  is_beta_tester BOOLEAN DEFAULT false,
  email_preferences JSONB DEFAULT '{"writing_submission": true, "marking_complete": true}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Validation Rules

### All Question Types

1. `type` must be a valid QuestionType string
2. `topic_id` must reference an existing topic
3. `content` should not be empty
4. `difficulty` must be 1-5

### Multiple Choice Types

1. Exactly ONE choice must have `is_correct: true`
2. All other choices must have `is_correct: false`
3. Minimum 2 choices required
4. Maximum typically 5 choices
5. Each choice needs `id` and `text`

### Multiple Choice with Images

1. All rules from multiple choice apply
2. EVERY choice must have `image` field with valid URL
3. URLs should point to accessible image files

### Drag and Drop

1. Uses `correct_position`, NOT `is_correct`
2. `correct_position` values must start at 1 (not 0)
3. Positions must be sequential (1, 2, 3... no gaps)
4. `correct_position: null` marks distractors
5. `max_positions` must equal count of non-null positions
6. At least 2 items with valid positions required

### Multi-Subquestion

1. Each choice needs `id`, `text`, and `correct`
2. `correct` must be a letter (A, B, C, etc.)
3. `extract_id` array must have corresponding extracts
4. Number of letters used cannot exceed number of extracts
5. At least one subquestion required

### Cloze

1. `{{N}}` in content must match choice `id` values
2. Each blank needs `options` array with EXACTLY 4 items
3. `is_correct` must be 0, 1, 2, or 3
4. `text` field should be empty string
5. At least one blank required

### Writing

1. `choices` MUST be `null` (not empty array)
2. `marking_criteria` should have at least one criterion
3. Each criterion needs `id`, `name`, `max_marks`, `description`
4. `max_marks` must be positive numbers

---

## Implementation Patterns

### Checking Correct Answer (MCQ)

```typescript
function checkMultipleChoice(question: QuestionFormData, answer: MultipleChoiceAnswer): boolean {
  const correctChoice = question.choices.find(c => c.is_correct === true);
  return correctChoice ? answer.selected === correctChoice.id : false;
}
```

### Checking Drag and Drop Answer

```typescript
function checkDragAndDrop(question: QuestionFormData, answer: DragAndDropAnswer): boolean {
  const correctOrder = question.choices
    .filter(c => c.correct_position !== null)
    .sort((a, b) => (a.correct_position || 0) - (b.correct_position || 0))
    .map(c => c.id);

  return JSON.stringify(answer.order) === JSON.stringify(correctOrder);
}
```

### Calculating Cloze Partial Credit

```typescript
function calculateClozeScore(question: QuestionFormData, answer: ClozeAnswer): number {
  const totalBlanks = question.choices.length;
  if (totalBlanks === 0) return 0;

  const correctBlanks = question.choices.filter(choice =>
    answer.blanks[choice.id] === choice.is_correct
  ).length;

  return correctBlanks / totalBlanks; // Returns 0.0 to 1.0
}
```

### Calculating Multi-Subquestion Partial Credit

```typescript
function calculateMultiSubScore(question: QuestionFormData, answer: MultiSubquestionAnswer): number {
  const totalSubs = question.choices.length;
  if (totalSubs === 0) return 0;

  const correctSubs = question.choices.filter(choice =>
    answer.multiSubAnswers[choice.id] === choice.correct
  ).length;

  return correctSubs / totalSubs; // Returns 0.0 to 1.0
}
```

### Calculating Writing Score from Marking

```typescript
function calculateWritingScore(markingScore: MarkingCriteriaScore): { score: number; max: number; percentage: number } {
  const score = markingScore.criteria.reduce((sum, c) => sum + c.score, 0);
  const max = markingScore.criteria.reduce((sum, c) => sum + c.max_marks, 0);
  const percentage = max > 0 ? (score / max) * 100 : 0;

  return { score, max, percentage };
}
```

### Validating Question Data

```typescript
function validateQuestion(question: QuestionFormData): string[] {
  const errors: string[] = [];

  if (!question.content?.trim()) {
    errors.push('Content is required');
  }

  if (!question.type) {
    errors.push('Question type is required');
  }

  if (!question.topic_id) {
    errors.push('Topic is required');
  }

  switch (question.type) {
    case 'multiple-choice':
    case 'multiple-choice-with-images':
      const correctCount = question.choices.filter(c => c.is_correct === true).length;
      if (correctCount !== 1) {
        errors.push('Exactly one correct answer required');
      }
      if (question.choices.length < 2) {
        errors.push('At least 2 choices required');
      }
      break;

    case 'drag-and-drop':
      const validPositions = question.choices.filter(c => c.correct_position !== null);
      if (validPositions.length < 2) {
        errors.push('At least 2 items with positions required');
      }
      break;

    case 'cloze':
      question.choices.forEach((choice, i) => {
        if (!choice.options || choice.options.length !== 4) {
          errors.push(`Blank ${i + 1} must have exactly 4 options`);
        }
        if (typeof choice.is_correct !== 'number' || choice.is_correct < 0 || choice.is_correct > 3) {
          errors.push(`Blank ${i + 1} must have valid correct index (0-3)`);
        }
      });
      break;

    case 'writing':
      if (question.choices !== null) {
        errors.push('Writing questions must have null choices');
      }
      if (!question.marking_criteria?.length) {
        errors.push('Writing questions require marking criteria');
      }
      break;
  }

  return errors;
}
```

### Rendering Cloze Content

```typescript
function renderClozeContent(content: string, choices: Choice[]): string {
  let rendered = content;
  choices.forEach(choice => {
    const placeholder = `{{${choice.id}}}`;
    const dropdown = `<select data-blank-id="${choice.id}">
      ${choice.options?.map((opt, i) => `<option value="${i}">${opt}</option>`).join('')}
    </select>`;
    rendered = rendered.replace(placeholder, dropdown);
  });
  return rendered;
}
```

---

## Analytics Fields

### `most_common_choice` (JSONB)

Tracks the most frequently selected answer:

```json
{
  "choice": "B",
  "count": 45,
  "percentage": 67.2
}
```

### Statistics Calculation

```typescript
interface QuestionStats {
  total_attempts: number;
  percent_correct: number;
  most_common_choice: {
    choice: string;
    count: number;
    percentage: number;
  };
  average_time_spent: number;
}

// Updated automatically on answer submission
```

---

## Email Preferences Schema

Stored in `profiles.email_preferences` (JSONB):

```json
{
  "writing_submission": true,
  "marking_complete": true
}
```

**Fields:**
- `writing_submission`: Teacher receives email when student submits writing test
- `marking_complete`: Student receives email when their writing is marked

**Default:** Both `true`

---

## Quick Reference Card

| Type | Correct Field | Choices Format | Partial Credit |
|------|--------------|----------------|----------------|
| multiple-choice | `is_correct: true` | Array of choices | No |
| multiple-choice-with-images | `is_correct: true` | Array with `image` | No |
| drag-and-drop | `correct_position: N` | Array + `max_positions` | No |
| multi-subquestion | `correct: "A"` | Array of subquestions | Yes |
| cloze | `is_correct: 0-3` | Array with `options` | Yes |
| writing | N/A | `null` | Yes (rubric) |

---

## Version History

- **v1.0** - Initial comprehensive documentation
- Covers all 6 question types
- Includes TypeScript types, database schemas, validation rules
- Self-contained for export to other projects
