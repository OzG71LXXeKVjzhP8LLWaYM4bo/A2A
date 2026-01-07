# A2A Selective Test Generator

An Agent-to-Agent (A2A) based system for generating NSW Selective Schools practice exams using Google's Gemini API. Questions match authentic NSW Selective High School Placement Test formats.

## Overview

This project implements a multi-agent architecture using Google's [A2A Protocol](https://a2a-protocol.org/) to generate high-quality educational content. Each agent specializes in a specific task and communicates via the A2A standard.

```
┌─────────────────────────────────────────────────────────────┐
│                 ORCHESTRATOR (Port 5000)                     │
│                 REST API + Pipeline Coordination             │
└─────────────────────────┬───────────────────────────────────┘
                          │ A2A Protocol (parallel generation)
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐     ┌──────────┐     ┌─────────┐
    │ CONCEPT │────▶│ QUESTION │────▶│ QUALITY │
    │  GUIDE  │     │GENERATOR │     │ CHECKER │
    │ (5001)  │     │  (5002)  │     │ (5003)  │
    │         │     │          │     │         │
    │ Concept │     │ NSW Exam │     │ Verify  │
    │Selection│     │ Formats  │     │+ Revise │
    └─────────┘     └──────────┘     └─────────┘
         │                                 │
         └────────── Feedback Loop ────────┘
                    (max 3 revisions)
```

## Features

- **NSW Exam Formats**: Questions match authentic NSW Selective High School Placement Test patterns
- **Multi-Agent Pipeline**: ConceptGuide → QuestionGenerator → QualityChecker with feedback loop
- **Parallel Generation**: All subtopics generated concurrently for 3-5x faster exam creation
- **A2A Protocol**: Standard inter-agent communication via JSON-RPC over HTTP
- **Gemini Integration**: Uses Gemini Flash for question generation and routing decisions
- **Auto-Verification**: Questions verified with solver + adversarial checks, auto-revision on failure
- **Triple Image Generation**: LLM-routed pipeline with GeoSDF (geometry), Spatial (3D cubes), and CCJ (general diagrams)
- **SAT-Style Diagrams**: Clean, professional educational diagrams with precise geometry
- **Cloudflare R2 Storage**: Auto-upload generated images with public URLs
- **REST API**: FastAPI-based endpoints for easy integration
- **Async PostgreSQL**: High-performance database operations with asyncpg

## NSW Exam Question Formats

The generator produces questions matching authentic NSW Selective test patterns (based on Practice Test 1 analysis):

| Subtopic | Count | Format | Example |
|----------|-------|--------|---------|
| **Critical Thinking** | 7 | Argument evaluation | "Which statement most strengthens/weakens the argument?" |
| **Logical Reasoning** | 11 | Conditionals, constraints, logic grids | If-then reasoning, contrapositive, truth-teller puzzles |
| **Deduction** | 4 | Boxed premise + two characters reasoning | "Whose reasoning is correct? A only / B only / Both / Neither" |
| **Inference** | 4 | Premise + character with flawed statement | "Which sentence shows the mistake [Name] has made?" |
| **Numerical Reasoning** | 8 | Multi-step word problems | Rate problems, optimization, working backwards |
| **Spatial Reasoning** | 6 | Visual patterns and shapes | Net folding, cube views, shape transformation |

**Total: 40 questions** (matching NSW Selective exam)

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- PostgreSQL database
- Gemini API key

## Installation

```bash
# Clone or navigate to the project
cd A2A

# Install dependencies with uv
uv sync

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
```

## Configuration

Create a `.env` file with the following variables:

```env
# Gemini API (required)
GEMINI_API_KEY=your-gemini-api-key

# PostgreSQL Database
DB_HOST=your-db-host
DB_PORT=5432
DB_NAME=your-database
DB_USER=your-user
DB_PASSWORD=your-password

# Cloudflare R2 (optional, for image storage)
R2_ACCOUNT_ID=your-account-id
R2_BUCKET_NAME=your-bucket
R2_ACCESS_KEY=your-access-key
R2_SECRET_KEY=your-secret-key
R2_PUBLIC_URL=https://your-bucket-url
```

## Usage

### Run All Agents

```bash
uv run python main.py all
```

This starts all agents on their respective ports:
- Orchestrator: http://localhost:5000
- Concept Guide: http://localhost:5001
- Question Generator: http://localhost:5002
- Quality Checker: http://localhost:5003

### Run Individual Agents

```bash
# Run in separate terminals
uv run python main.py orchestrator
uv run python main.py concept_guide
uv run python main.py question_generator
uv run python main.py quality_checker
```

### Generate an Exam

```bash
# Generate a Thinking Skills exam
curl -X POST http://localhost:5000/api/exams/thinking-skills \
  -H "Content-Type: application/json" \
  -d '{
    "exam_name": "Practice Test 1",
    "time_limit": 45,
    "enable_images": true,
    "analogies_count": 4,
    "pattern_recognition_count": 5,
    "logical_count": 5,
    "spatial_reasoning_count": 4
  }'
```

## API Reference

### Health Check
```
GET /health
```

### List Agents
```
GET /agents
```
Returns status of all connected agents.

### Generate Exam
```
POST /api/exams/generate
Content-Type: application/json

{
  "exam_type": "thinking_skills",
  "config": {
    "exam_name": "My Exam",
    "time_limit": 45,
    "enable_images": true
  }
}
```

### Generate Thinking Skills Exam
```
POST /api/exams/thinking-skills
Content-Type: application/json

{
  "critical_thinking_count": 7,
  "logical_reasoning_count": 11,
  "deduction_count": 4,
  "inference_count": 4,
  "numerical_reasoning_count": 8,
  "spatial_reasoning_count": 6,
  "enable_images": true,
  "custom_instructions": ""
}
```

Default generates 40 questions (matching NSW Selective exam distribution based on Practice Test 1).

**Performance**: ~90-120 seconds for 40 questions (parallel subtopic generation).

### Generate Math Exam
```
POST /api/exams/math
Content-Type: application/json

{
  "geometry_count": 5,
  "fractions_count": 4,
  "percentages_count": 4,
  ...
}
```

## Agents

### Orchestrator Agent (Port 5000)

The main coordinator that:
- Exposes REST API endpoints
- Coordinates the multi-agent pipeline
- Runs subtopics in parallel for fast generation
- Aggregates results into complete exams

### Concept Guide Agent (Port 5001)

Manages the concept curriculum and selects what to test:
- Loads concept definitions from `data/concepts/`
- Selects appropriate concepts based on subtopic and difficulty
- Tracks misconceptions for distractor design
- Provides concept context to the question generator

### Question Generator Agent (Port 5002)

Creates questions using NSW Selective exam formats:
- Loads subtopic-specific prompts from `prompts/thinking-skills/subtopics/`
- Uses format templates matching real NSW exams (boxed premises, character dialogues)
- Generates blueprint + realized question in one step
- Handles revision requests from quality checker

**Subtopic-specific formats:**
- **Deduction**: HTML box with premise, character statements, "Whose reasoning is correct?"
- **Inference**: Premise content + character portrait with flawed statement
- **Critical Thinking**: Argument + strengthen/weaken analysis

### Quality Checker Agent (Port 5003)

Validates questions with a multi-stage pipeline:

```
Question → Solve → Attack → Judge → PASS? → Done
                              ↓
                            FAIL
                              ↓
                   Return issues + suggestions
                              ↓
                   Question Generator revises
                              ↓
                        Re-check
                              ↓
                   (loop max 3 times)
```

**Verification stages:**
1. **Solver** - Independently solves the question to verify the marked answer
2. **Attacker** - Finds ambiguities, shortcuts, or alternative valid answers
3. **Judge** - Makes final accept/reject decision with specific feedback

### Image Agent (future)

Generates SAT-style educational diagrams using an LLM-routed triple approach:

```
                              ┌─── Spatial (3D cubes)
                              │         ↓
Description → LLM Router ─────┼─── GeoSDF (geometry)
                              │         ↓
                              └─── CCJ (general)
                                      ↓
                              Matplotlib / CairoSVG
                                      ↓
                              R2 Upload → Public URL
```

**Spatial** - For 3D cube stack questions (100% programmatic, no LLM):
- Generates random cube arrangements (difficulty-based: easy/medium/hard)
- Two question types:
  - `find_view`: Given 3D shape → identify correct 2D view
  - `find_shape`: Given 2D view → identify correct 3D shape
- Renders dual isometric views (azim=45° and 225°) with FRONT/RIGHT/BACK/LEFT labels
- Generates orthographic projections (top/front/right/left) as consistent silhouettes
- Returns question images + 4 multiple-choice options with correct answer
- Use cases: "Which is the front view?", "Which shape has this top view?"

**GeoSDF** (arxiv 2506.13492v2) - For precise 2D geometry:
- Parses description → symbolic elements + constraints via Gemini
- PyTorch-based constraint optimization (AdamW + cosine annealing)
- Smart label positioning (perpendicular offsets, angle arcs)
- Renders with Matplotlib
- Use cases: triangles, angles, parallel lines, circles, geometric proofs

**CCJ** (arxiv 2508.15222) - For general diagrams:
- Critic-Candidates-Judge loop with Gemini
- Generates 3 SVG candidates with different strategies
- Judge selects best, Critic refines
- Renders with CairoSVG
- Use cases: Venn diagrams, flowcharts, number lines, coordinate planes

**LLM Router**: Gemini Flash classifies each request to choose the appropriate generator.

### Database Agent (Port 5003)

Handles PostgreSQL operations:
- Insert questions to questionbank
- Create exam records
- Link questions to exams
- Query subtopics

## Project Structure

```
A2A/
├── main.py                 # Entry point
├── config.py               # Configuration management
├── pyproject.toml          # Dependencies
├── .env.example            # Environment template
├── exam_viewer.html        # Interactive exam viewer/taker
│
├── agents/
│   ├── base_agent.py       # Base class with Gemini integration
│   ├── orchestrator.py     # REST API + pipeline coordination
│   ├── pipeline_controller.py  # Manages question generation flow
│   ├── concept_guide_agent.py  # Concept selection from curriculum
│   ├── question_generator_agent.py  # NSW-format question creation
│   └── quality_checker_agent.py     # Solver + Attacker + Judge
│
├── a2a_local/
│   ├── server.py           # A2A server (JSON-RPC)
│   └── client.py           # A2A client for inter-agent calls
│
├── models/
│   ├── question.py         # Question/Exam Pydantic models
│   ├── blueprint.py        # Question blueprint models
│   ├── judgment.py         # Quality judgment models
│   └── curriculum.py       # Concept/curriculum models
│
├── data/
│   └── concepts/
│       └── thinking_skills/  # Concept definitions per subtopic
│           ├── deduction.json
│           ├── inference.json
│           ├── critical_thinking.json
│           └── ...
│
├── prompts/
│   └── thinking-skills/
│       └── subtopics/      # NSW exam format prompts
│           ├── deduction.md    # "Whose reasoning is correct?"
│           ├── inference.md    # "Which sentence shows the mistake?"
│           ├── critical_thinking.md
│           └── ...
│
└── tests/
```

## Image Generation Strategy

The LLM Router automatically selects the best approach:

| Image Type | Method | Why |
|------------|--------|-----|
| 3D cube stacks, block arrangements | Spatial | Programmatic 3D + orthographic views |
| "Which is the front view?" (3D→2D) | Spatial | find_view question type |
| "Which shape has this view?" (2D→3D) | Spatial | find_shape question type |
| Triangles, angles, geometric proofs | GeoSDF | Constraint-based precision |
| Parallel lines, perpendiculars | GeoSDF | Exact angle relationships |
| Circles with tangents/chords | GeoSDF | Mathematical accuracy |
| Venn diagrams | CCJ | Conceptual, not geometric |
| Flowcharts, trees | CCJ | Relationship-focused |
| Number lines, coordinate planes | CCJ | SVG grid generation |
| Bar/pie charts | CCJ | Visual representation |

### Spatial Output Format

Spatial questions return a complete multiple-choice structure:

**find_view** (3D → 2D): Given 3D shape, find the correct 2D view
```json
{
  "success": true,
  "generation_method": "spatial",
  "metadata": {
    "question_type": "find_view",
    "question_images": ["3d_view1.png", "3d_view2.png"],
    "view_type": "front",
    "options": ["2d_A.png", "2d_B.png", "2d_C.png", "2d_D.png"],
    "correct_index": 2,
    "answer": "C"
  }
}
```

**find_shape** (2D → 3D): Given 2D view, find the correct 3D shape
```json
{
  "success": true,
  "generation_method": "spatial",
  "metadata": {
    "question_type": "find_shape",
    "question_images": ["2d_view.png"],
    "view_type": "front",
    "options": [
      ["shape_A_iso1.png", "shape_A_iso2.png"],
      ["shape_B_iso1.png", "shape_B_iso2.png"],
      ["shape_C_iso1.png", "shape_C_iso2.png"],
      ["shape_D_iso1.png", "shape_D_iso2.png"]
    ],
    "correct_index": 1,
    "answer": "B"
  }
}
```

Quality criteria (SAT-style):
- Pure white background
- Black lines (2px weight)
- Sans-serif labels (Arial)
- No gradients, shadows, or 3D effects
- Clean geometric precision

Test prompts available in `prompts/image_test_prompts.json` (45 prompts covering both methods).

## Logging

The system includes comprehensive logging of all agent communications and LLM calls.

### Enable Logging

Logging is enabled by default. Control via environment variables:

```bash
# Set log level (DEBUG, INFO, WARNING, ERROR)
export A2A_LOG_LEVEL=INFO

# Enable verbose mode (shows full prompts/responses)
export A2A_LOG_VERBOSE=true

# Toggle LLM call logging
export A2A_LOG_LLM=true

# Toggle agent message logging
export A2A_LOG_MESSAGES=true
```

### Log Output

The logs show:
- **Agent Messages**: All A2A protocol messages between agents (SEND/RECEIVE)
- **LLM Calls**: Prompts sent to Gemini and responses received (with timing)
- **Pipeline Steps**: Progress through the question generation pipeline
- **Errors**: Any errors with context

Example output:
```
────────────────────────────────────────────────────────────────────────────────
[14:32:15.123] SEND Orchestrator → concept_guide (select_concept)
{"action": "select_concept", "subtopic": "Deduction", "difficulty": 3}
────────────────────────────────────────────────────────────────────────────────
[14:32:15.456] STEP 1/3: Select Concept
  subtopic=Deduction, difficulty=3
════════════════════════════════════════════════════════════════════════════════
[14:32:16.789] LLM CALL QuestionGeneratorAgent (gemini-2.0-flash)

PROMPT:
You are creating a NSW Selective Schools exam question...

RESPONSE (2340ms):
{"setup_elements": ["premise about scores"], "question_text": "Whose reasoning is correct?"...}
════════════════════════════════════════════════════════════════════════════════
```

### Color Coding

- **Magenta**: Orchestrator messages
- **Blue**: Concept Guide messages
- **Green**: Question Generator messages
- **Yellow**: Quality Checker messages
- **Cyan**: Outgoing messages (SEND)
- **White**: Incoming messages (RECEIVE)

## Development

### Adding a New Agent

1. Create a new file in `agents/`:
```python
from agents.base_agent import BaseAgent
from a2a import AgentConfig

class MyAgent(BaseAgent):
    def __init__(self):
        agent_config = AgentConfig(
            name="MyAgent",
            description="Does something useful",
            port=5005,
            skills=[...],
        )
        super().__init__(agent_config)

    async def handle_task(self, task, context):
        # Handle incoming A2A tasks
        pass
```

2. Register in `main.py`
3. Add endpoint to `a2a/client.py`

### Testing

```bash
# Run tests
uv run pytest tests/

# Test a single agent
uv run python -c "
import asyncio
from agents.thinking_skills_agent import ThinkingSkillsAgent

async def test():
    agent = ThinkingSkillsAgent()
    result = await agent.generate_questions('pattern_recognition', 2, False)
    print(result)

asyncio.run(test())
"
```

## Tech Stack

- **[uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[google-genai](https://pypi.org/project/google-genai/)** - Gemini API SDK
- **[a2a-sdk](https://pypi.org/project/a2a-sdk/)** - A2A Protocol implementation
- **[FastAPI](https://fastapi.tiangolo.com/)** - REST API framework
- **[asyncpg](https://github.com/MagicStack/asyncpg)** - Async PostgreSQL driver
- **[PyTorch](https://pytorch.org/)** - GeoSDF constraint optimization
- **[CairoSVG](https://cairosvg.org/)** - SVG to PNG rendering
- **[Matplotlib](https://matplotlib.org/)** - GeoSDF diagram rendering
- **[boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)** - Cloudflare R2 uploads

## Related Resources

- [A2A Protocol Documentation](https://a2a-protocol.org/)
- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
- [GeoSDF Paper (arxiv 2506.13492v2)](https://arxiv.org/abs/2506.13492) - Constraint-based geometry generation
- [CCJ Paper (arxiv 2508.15222)](https://arxiv.org/abs/2508.15222) - Critic-Candidates-Judge loop
- [Original n8n Workflow](../Selective-test-n8n-workflow/)

## License

MIT
