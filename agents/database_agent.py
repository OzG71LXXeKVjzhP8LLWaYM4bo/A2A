"""Database Agent for PostgreSQL operations."""

import asyncio
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import asyncpg

from a2a_local import AgentConfig
from agents.base_agent import BaseAgent
from models import Question, Exam
from config import config


class DatabaseAgent(BaseAgent):
    """Agent for database operations."""

    def __init__(self):
        agent_config = AgentConfig(
            name="DatabaseAgent",
            description="Handles PostgreSQL operations for questions and exams",
            port=config.ports.database,
            skills=[
                {
                    "id": "insert_questions",
                    "name": "Insert Questions",
                    "description": "Insert questions into the questionbank",
                    "tags": ["database", "insert"],
                },
                {
                    "id": "create_exam",
                    "name": "Create Exam",
                    "description": "Create an exam record and link questions",
                    "tags": ["database", "exam"],
                },
                {
                    "id": "get_subtopics",
                    "name": "Get Subtopics",
                    "description": "Fetch subtopics for a topic",
                    "tags": ["database", "query"],
                },
            ],
        )
        super().__init__(agent_config)
        self._pool: Optional[asyncpg.Pool] = None

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                config.database.connection_string,
                min_size=2,
                max_size=10,
            )
        return self._pool

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
                return {"error": "Invalid JSON in task message"}
        else:
            return {"error": "No task data provided"}

        action = task_data.get("action", "")

        if action == "insert_questions":
            return await self.insert_questions(task_data.get("questions", []))
        elif action == "create_exam":
            return await self.create_exam(
                exam_data=task_data.get("exam", {}),
                question_ids=task_data.get("question_ids", []),
            )
        elif action == "get_subtopics":
            return await self.get_subtopics(task_data.get("topic_id"))
        else:
            return {"error": f"Unknown action: {action}"}

    async def insert_questions(self, questions: list[dict]) -> dict:
        """Insert questions into the questionbank."""
        pool = await self.get_pool()
        inserted_ids = []
        errors = []

        async with pool.acquire() as conn:
            for q_data in questions:
                try:
                    # Generate UUID if not provided
                    question_id = q_data.get("id") or str(uuid4())

                    # Convert choices to JSON
                    choices = json.dumps(q_data.get("choices", []))

                    # Build insert query - matching n8n schema
                    query = """
                        INSERT INTO questionbank (
                            id, question, content, choices, explanation, type,
                            difficulty, topic_id, subtopic_ids, tags,
                            showup, is_active, created_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            question = EXCLUDED.question,
                            choices = EXCLUDED.choices,
                            explanation = EXCLUDED.explanation,
                            updated_at = NOW()
                        RETURNING id
                    """

                    # Get subtopic_id from database if subtopic_name provided
                    subtopic_id = q_data.get("subtopic_id")
                    if not subtopic_id and q_data.get("subtopic_name"):
                        subtopic_id = await self._get_subtopic_id(
                            conn, q_data["subtopic_name"]
                        )

                    # Convert subtopic_id to array for subtopic_ids column
                    subtopic_ids = [subtopic_id] if subtopic_id else None

                    # Get topic_id
                    topic_id = q_data.get("topic_id")
                    if isinstance(topic_id, str):
                        topic_id = UUID(topic_id)

                    result = await conn.fetchval(
                        query,
                        UUID(question_id) if isinstance(question_id, str) else question_id,
                        q_data["question"],
                        q_data.get("content"),
                        choices,
                        q_data.get("explanation", ""),
                        q_data.get("type", "multiple-choice"),
                        str(q_data.get("difficulty", "2")),
                        topic_id,
                        subtopic_ids,
                        q_data.get("tags", []),
                        q_data.get("showup", True),
                        q_data.get("is_active", True),
                        datetime.utcnow(),
                    )
                    inserted_ids.append(str(result))

                except Exception as e:
                    errors.append({
                        "question": q_data.get("question", "unknown")[:50],
                        "error": str(e),
                    })

        return {
            "success": len(errors) == 0,
            "inserted_count": len(inserted_ids),
            "inserted_ids": inserted_ids,
            "errors": errors,
        }

    async def _get_subtopic_id(
        self, conn: asyncpg.Connection, subtopic_name: str
    ) -> Optional[UUID]:
        """Get subtopic ID from name."""
        query = "SELECT id FROM subtopics WHERE name = $1 LIMIT 1"
        result = await conn.fetchval(query, subtopic_name)
        return result

    async def create_exam(
        self,
        exam_data: dict,
        question_ids: list[str],
    ) -> dict:
        """Create an exam and link questions."""
        pool = await self.get_pool()

        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Generate exam code if not provided
                    now = datetime.utcnow()
                    exam_code = exam_data.get("code") or f"EXAM-{now.strftime('%Y%m%d-%H%M')}"
                    exam_name = exam_data.get("name") or f"Exam {exam_code}"
                    exam_id = exam_data.get("id") or str(uuid4())

                    # Insert exam - matching n8n schema with type and question_count
                    exam_query = """
                        INSERT INTO exams (
                            id, code, name, description, type, time_limit,
                            question_count, topic_id, is_active, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        RETURNING id
                    """

                    topic_id = exam_data.get("topic_id")
                    if isinstance(topic_id, str):
                        topic_id = UUID(topic_id)

                    # Get question_count - either from exam_data or from question_ids length
                    question_count = exam_data.get("question_count", len(question_ids))

                    result = await conn.fetchval(
                        exam_query,
                        UUID(exam_id) if isinstance(exam_id, str) else exam_id,
                        exam_code,
                        exam_name,
                        exam_data.get("description", ""),
                        exam_data.get("type", "thinking-skills"),
                        exam_data.get("time_limit", 45),
                        question_count,
                        topic_id,
                        exam_data.get("is_active", True),
                        now,
                    )
                    exam_id = result

                    # Link questions to exam
                    link_query = """
                        INSERT INTO exam_questions (exam_id, question_id, question_order)
                        VALUES ($1, $2, $3)
                    """

                    for order, q_id in enumerate(question_ids, 1):
                        await conn.execute(
                            link_query,
                            exam_id,
                            UUID(q_id) if isinstance(q_id, str) else q_id,
                            order,
                        )

                    return {
                        "success": True,
                        "exam_id": str(exam_id),
                        "exam_code": exam_code,
                        "questions_linked": len(question_ids),
                    }

                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                    }

    async def get_subtopics(self, topic_id: Optional[str] = None) -> dict:
        """Fetch subtopics, optionally filtered by topic."""
        pool = await self.get_pool()

        async with pool.acquire() as conn:
            try:
                if topic_id:
                    query = """
                        SELECT id, name, description, topic_id
                        FROM subtopics
                        WHERE topic_id = $1
                        ORDER BY name
                    """
                    rows = await conn.fetch(query, UUID(topic_id))
                else:
                    query = """
                        SELECT id, name, description, topic_id
                        FROM subtopics
                        ORDER BY topic_id, name
                    """
                    rows = await conn.fetch(query)

                subtopics = [
                    {
                        "id": str(row["id"]),
                        "name": row["name"],
                        "description": row["description"],
                        "topic_id": str(row["topic_id"]) if row["topic_id"] else None,
                    }
                    for row in rows
                ]

                return {
                    "success": True,
                    "subtopics": subtopics,
                    "count": len(subtopics),
                }

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

    async def close(self):
        """Close the database pool."""
        if self._pool:
            await self._pool.close()


async def main():
    """Run the Database Agent."""
    agent = DatabaseAgent()
    print(f"Starting Database Agent on port {config.ports.database}...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
