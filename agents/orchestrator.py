"""Orchestrator Agent for coordinating the exam generation workflow."""

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from a2a_local import AgentConfig, A2AClient, AGENT_ENDPOINTS
from agents.base_agent import BaseAgent
from agents.pipeline_controller import PipelineController, PipelineConfig
from models import ThinkingSkillsConfig, MathConfig, PipelineResult
from config import config


class GenerateExamRequest(BaseModel):
    exam_type: str  # "thinking_skills", "math", "reading"
    config: dict = {}


class OrchestratorAgent(BaseAgent):
    """Main orchestrator agent that coordinates the exam generation workflow."""

    def __init__(self):
        agent_config = AgentConfig(
            name="OrchestratorAgent",
            description="Coordinates exam generation across specialized agents",
            port=config.ports.orchestrator,
            skills=[
                {
                    "id": "generate_exam",
                    "name": "Generate Exam",
                    "description": "Generate a complete exam by orchestrating sub-agents",
                    "tags": ["orchestration", "exam"],
                },
                {
                    "id": "check_agents",
                    "name": "Check Agents",
                    "description": "Check status of all sub-agents",
                    "tags": ["health", "status"],
                },
            ],
        )
        super().__init__(agent_config)
        self.a2a_client = A2AClient(timeout=300.0, caller_name="Orchestrator")
        self.pipeline = PipelineController(
            client=self.a2a_client,
            config=PipelineConfig(max_revisions=3),
        )

    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle incoming task requests."""
        message = task.status.message
        if message and message.parts:
            # A2A SDK wraps parts - access via .root.text for TextPart
            part = message.parts[0]
            task_text = part.root.text if hasattr(part, 'root') else part.text
            try:
                task_data = json.loads(task_text)
            except json.JSONDecodeError:
                task_data = {"action": "generate_exam", "exam_type": "thinking_skills"}
        else:
            task_data = {"action": "generate_exam", "exam_type": "thinking_skills"}

        action = task_data.get("action", "generate_exam")

        if action == "generate_exam":
            return await self.generate_exam(
                exam_type=task_data.get("exam_type", "thinking_skills"),
                exam_config=task_data.get("config", {}),
            )
        elif action == "check_agents":
            return await self.check_agents()
        else:
            return {"error": f"Unknown action: {action}"}

    async def check_agents(self) -> dict:
        """Check status of all sub-agents."""
        statuses = {}

        for name, endpoint in AGENT_ENDPOINTS.items():
            if name == "orchestrator":
                continue  # Skip self

            try:
                card = await self.a2a_client.get_agent_card(endpoint)
                statuses[name] = {
                    "status": "online" if card else "offline",
                    "url": endpoint.base_url,
                    "skills": [s.name for s in card.skills] if card else [],
                }
            except Exception as e:
                statuses[name] = {
                    "status": "error",
                    "url": endpoint.base_url,
                    "error": str(e),
                }

        return {
            "agents": statuses,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def generate_exam(
        self,
        exam_type: str,
        exam_config: dict,
    ) -> dict:
        """Generate a complete exam by orchestrating sub-agents."""

        # Validate exam type
        if exam_type not in ["thinking_skills", "math", "reading"]:
            return {"error": f"Unsupported exam type: {exam_type}"}

        # Generate exam code
        now = datetime.utcnow()
        prefix = {"thinking_skills": "THINK", "math": "MATH", "reading": "READ"}
        exam_code = exam_config.get("exam_code") or f"{prefix[exam_type]}-{now.strftime('%Y%m%d-%H%M')}"
        exam_name = exam_config.get("exam_name") or f"{exam_type.replace('_', ' ').title()} Exam {exam_code}"

        result = {
            "exam_code": exam_code,
            "exam_name": exam_name,
            "exam_type": exam_type,
            "steps": [],
        }

        # Step 1: Generate questions via specialized agent
        result["steps"].append({"step": "generate_questions", "status": "in_progress"})

        if exam_type == "thinking_skills":
            questions_result = await self._generate_thinking_skills(exam_config)
        elif exam_type == "math":
            questions_result = await self._generate_math(exam_config)
        else:
            questions_result = {"error": "Reading agent not implemented yet"}

        if not questions_result.get("success"):
            result["steps"][-1]["status"] = "failed"
            result["steps"][-1]["error"] = questions_result.get("error", "Unknown error")
            result["success"] = False
            return result

        result["steps"][-1]["status"] = "completed"
        result["steps"][-1]["question_count"] = questions_result.get("total_questions", 0)

        questions = questions_result.get("questions", [])

        # Step 2: Generate images for questions that need them
        questions_needing_images = [q for q in questions if q.get("requires_image")]

        if questions_needing_images:
            result["steps"].append({
                "step": "generate_images",
                "status": "in_progress",
                "count": len(questions_needing_images),
            })

            for q in questions_needing_images:
                image_result = await self._generate_image(q.get("image_description", ""))
                if image_result.get("success"):
                    q["image_url"] = f"data:image/png;base64,{image_result.get('image_base64', '')}"

            result["steps"][-1]["status"] = "completed"

        # Step 3: Insert questions to database
        result["steps"].append({"step": "insert_questions", "status": "in_progress"})

        db_result = await self._insert_questions(questions)

        if not db_result.get("success"):
            result["steps"][-1]["status"] = "failed"
            result["steps"][-1]["error"] = db_result.get("error", "Database error")
            # Continue anyway - questions were generated
        else:
            result["steps"][-1]["status"] = "completed"
            result["steps"][-1]["inserted_count"] = db_result.get("inserted_count", 0)
            question_ids = db_result.get("inserted_ids", [])

            # Step 4: Create exam record
            result["steps"].append({"step": "create_exam", "status": "in_progress"})

            topic_id = config.topic_uuids.get(exam_type)
            # Convert exam_type to hyphenated format for database (e.g., "thinking_skills" -> "thinking-skills")
            exam_type_db = exam_type.replace("_", "-")
            exam_result = await self._create_exam(
                exam_data={
                    "code": exam_code,
                    "name": exam_name,
                    "description": exam_config.get("exam_description", ""),
                    "type": exam_type_db,
                    "time_limit": exam_config.get("time_limit", 45),
                    "question_count": len(question_ids),
                    "topic_id": topic_id,
                },
                question_ids=question_ids,
            )

            if exam_result.get("success"):
                result["steps"][-1]["status"] = "completed"
                result["exam_id"] = exam_result.get("exam_id")

                # Step 5: Add exam to pack if pack_id provided
                pack_id = exam_config.get("pack_id")
                if pack_id and result.get("exam_id"):
                    result["steps"].append({"step": "add_to_pack", "status": "in_progress"})

                    pack_result = await self._add_exam_to_pack(
                        exam_id=result["exam_id"],
                        pack_id=pack_id,
                    )

                    if pack_result.get("success"):
                        result["steps"][-1]["status"] = "completed"
                        result["steps"][-1]["pack_id"] = pack_id
                        result["steps"][-1]["exam_order"] = pack_result.get("exam_order")
                        result["pack_id"] = pack_id
                    else:
                        result["steps"][-1]["status"] = "failed"
                        result["steps"][-1]["error"] = pack_result.get("error", "")
            else:
                result["steps"][-1]["status"] = "failed"
                result["steps"][-1]["error"] = exam_result.get("error", "")

        result["success"] = True
        result["total_questions"] = len(questions)
        result["questions"] = questions  # Include for review

        return result

    async def _generate_thinking_skills(self, exam_config: dict) -> dict:
        """Generate thinking skills questions using the multi-agent pipeline."""
        # Get subtopic distribution from config
        subtopic_questions = exam_config.get("subtopic_questions", {})
        total_questions = exam_config.get("total_questions", 35)
        difficulty = exam_config.get("difficulty", 3)

        # Default distribution if not specified
        if not subtopic_questions:
            # Map subtopic names to keys used in concept files
            subtopic_keys = [
                "analogies",
                "logical_reasoning",
                "pattern_recognition",
                "spatial_reasoning",
                "sequencing",
                "deduction",
                "inference",
                "critical_thinking",
            ]
            questions_per_subtopic = total_questions // len(subtopic_keys)
            remainder = total_questions % len(subtopic_keys)

            for i, key in enumerate(subtopic_keys):
                subtopic_questions[key] = questions_per_subtopic + (1 if i < remainder else 0)

        all_questions = []
        errors = []

        # Generate all subtopics in PARALLEL for speed
        tasks = []
        subtopic_names = []
        for subtopic, count in subtopic_questions.items():
            if count <= 0:
                continue
            print(f"Queuing {count} questions for {subtopic}...")
            tasks.append(self.pipeline.generate_batch(
                subtopic=subtopic,
                count=count,
                difficulty=difficulty,
            ))
            subtopic_names.append(subtopic)

        print(f"Generating {len(tasks)} subtopics in parallel...")
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results from all subtopics
        for subtopic, results in zip(subtopic_names, all_results):
            if isinstance(results, Exception):
                errors.append(f"Error generating {subtopic}: {str(results)}")
                continue

            for result in results:
                if result.accepted and result.question:
                    # Question is already a dict from pipeline
                    q_dict = result.question if isinstance(result.question, dict) else result.question.model_dump(mode="json")
                    all_questions.append(q_dict)
                else:
                    errors.extend(result.errors)

        return {
            "success": True,
            "questions": all_questions,
            "total_questions": len(all_questions),
            "errors": errors if errors else None,
        }

    async def _generate_math(self, exam_config: dict) -> dict:
        """Send task to Math Agent."""
        endpoint = AGENT_ENDPOINTS["math"]

        task_message = json.dumps({
            "action": "generate_exam",
            "config": exam_config,
        })

        return await self.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="generate_exam",
            message=task_message,
        )

    async def _generate_image(self, description: str) -> dict:
        """Send task to Image Agent."""
        endpoint = AGENT_ENDPOINTS["image"]

        task_message = json.dumps({
            "action": "generate_diagram",
            "description": description,
            "max_attempts": 3,
        })

        return await self.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="generate_diagram",
            message=task_message,
        )

    async def _insert_questions(self, questions: list[dict]) -> dict:
        """Send task to Database Agent."""
        endpoint = AGENT_ENDPOINTS["database"]

        task_message = json.dumps({
            "action": "insert_questions",
            "questions": questions,
        })

        return await self.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="insert_questions",
            message=task_message,
        )

    async def _create_exam(
        self,
        exam_data: dict,
        question_ids: list[str],
    ) -> dict:
        """Send task to Database Agent."""
        endpoint = AGENT_ENDPOINTS["database"]

        task_message = json.dumps({
            "action": "create_exam",
            "exam": exam_data,
            "question_ids": question_ids,
        })

        return await self.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="create_exam",
            message=task_message,
        )

    async def _add_exam_to_pack(
        self,
        exam_id: str,
        pack_id: str,
    ) -> dict:
        """Send task to Database Agent to add exam to a pack."""
        endpoint = AGENT_ENDPOINTS["database"]

        task_message = json.dumps({
            "action": "add_exam_to_pack",
            "exam_id": exam_id,
            "pack_id": pack_id,
        })

        return await self.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="add_exam_to_pack",
            message=task_message,
        )


# FastAPI app for REST API
def create_api_app() -> FastAPI:
    """Create FastAPI app with REST endpoints."""
    app = FastAPI(
        title="Selective Test Generator API",
        description="A2A-based exam generation system",
        version="1.0.0",
    )

    # Add CORS middleware for browser requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    orchestrator = OrchestratorAgent()

    @app.get("/health")
    async def health():
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

    @app.get("/agents")
    async def list_agents():
        return await orchestrator.check_agents()

    @app.post("/api/exams/generate")
    async def generate_exam(request: GenerateExamRequest):
        result = await orchestrator.generate_exam(
            exam_type=request.exam_type,
            exam_config=request.config,
        )
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))
        return result

    @app.post("/api/exams/thinking-skills")
    async def generate_thinking_skills(config: dict = {}):
        result = await orchestrator.generate_exam(
            exam_type="thinking_skills",
            exam_config=config,
        )
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))
        return result

    @app.post("/api/exams/math")
    async def generate_math(config: dict = {}):
        result = await orchestrator.generate_exam(
            exam_type="math",
            exam_config=config,
        )
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))
        return result

    @app.get("/api/packs")
    async def list_packs():
        """List available exam packs."""
        endpoint = AGENT_ENDPOINTS["database"]
        task_message = json.dumps({"action": "get_exam_packs"})

        result = await orchestrator.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="get_exam_packs",
            message=task_message,
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch packs"))
        return result

    @app.get("/api/concepts")
    async def list_concepts():
        """List all available subtopics and concepts."""
        endpoint = AGENT_ENDPOINTS["concept_guide"]
        task_message = json.dumps({"action": "list_subtopics"})

        result = await orchestrator.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="list_subtopics",
            message=task_message,
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to fetch concepts"))
        return result

    @app.get("/api/concepts/{subtopic}")
    async def get_concepts(subtopic: str):
        """Get concepts for a specific subtopic."""
        endpoint = AGENT_ENDPOINTS["concept_guide"]
        task_message = json.dumps({
            "action": "get_concepts",
            "subtopic": subtopic,
        })

        result = await orchestrator.a2a_client.send_task(
            endpoint=endpoint,
            skill_id="get_concepts",
            message=task_message,
        )

        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Subtopic not found"))
        return result

    @app.post("/api/questions/blueprint")
    async def generate_blueprint(request: dict):
        """Generate a question blueprint (for debugging/testing)."""
        subtopic = request.get("subtopic", "analogies")
        difficulty = request.get("difficulty", 3)

        # Step 1: Select concept
        concept_result = await orchestrator.a2a_client.send_task(
            endpoint=AGENT_ENDPOINTS["concept_guide"],
            skill_id="select_concept",
            message=json.dumps({
                "action": "select_concept",
                "subtopic": subtopic,
                "difficulty": difficulty,
            }),
        )

        if not concept_result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to select concept")

        # Step 2: Generate question (includes blueprint)
        gen_result = await orchestrator.a2a_client.send_task(
            endpoint=AGENT_ENDPOINTS["question_generator"],
            skill_id="generate_question",
            message=json.dumps({
                "action": "generate_question",
                "selection": concept_result.get("selection"),
            }),
        )

        if not gen_result.get("success"):
            raise HTTPException(status_code=500, detail="Failed to generate question")

        return {
            "concept": concept_result.get("selection", {}).get("concept"),
            "blueprint": gen_result.get("blueprint"),
            "question": gen_result.get("question"),
        }

    @app.post("/api/questions/single")
    async def generate_single_question(request: dict):
        """Generate a single question through the full pipeline."""
        subtopic = request.get("subtopic", "analogies")
        difficulty = request.get("difficulty", 3)

        result = await orchestrator.pipeline.generate_question(
            subtopic=subtopic,
            difficulty=difficulty,
        )

        return {
            "accepted": result.accepted,
            "question": result.question if isinstance(result.question, dict) else (result.question.model_dump(mode="json") if result.question else None),
            "revision_count": result.revision_count,
            "errors": result.errors,
            "judgment": result.judgment,
        }

    return app


async def main():
    """Run the Orchestrator Agent with REST API."""
    import uvicorn

    app = create_api_app()
    uvicorn_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=config.ports.orchestrator,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    print(f"Starting Orchestrator Agent on port {config.ports.orchestrator}...")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
