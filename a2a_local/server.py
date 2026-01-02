"""A2A Server implementation using a2a-sdk."""

import asyncio
import uuid
from typing import Any, Callable, Optional
from dataclasses import dataclass

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Task,
    TaskState,
    Message,
    TextPart,
)
import uvicorn


@dataclass
class AgentConfig:
    name: str
    description: str
    port: int
    skills: list[dict]
    version: str = "1.0.0"


class BaseAgentExecutor(AgentExecutor):
    """Base agent executor that can be extended by specific agents."""

    def __init__(self, task_handler: Optional[Callable] = None):
        self._task_handler = task_handler

    async def execute(
        self,
        context: RequestContext,
        event_queue: asyncio.Queue,
    ) -> None:
        """Execute the agent task."""
        # Get current task from context
        task = context.current_task
        if task is None:
            # Create a minimal task from the request
            from a2a.types import TaskStatus
            task = Task(
                id=context.task_id or "temp-task",
                context_id=context.context_id or "temp-context",
                status=TaskStatus(state=TaskState.submitted),
            )
            # Copy message from request if available
            if context.message:
                task.status.message = context.message

        # Update task state to working
        task.status.state = TaskState.working
        await event_queue.enqueue_event(task)

        try:
            if self._task_handler:
                result = await self._task_handler(task, context)
            else:
                result = {"message": "No handler configured"}

            # Create response message
            response_message = Message(
                role="agent",
                message_id=str(uuid.uuid4()),
                parts=[TextPart(text=str(result))],
            )

            # Update task with result
            task.status.state = TaskState.completed
            task.status.message = response_message
            await event_queue.enqueue_event(task)

        except Exception as e:
            task.status.state = TaskState.failed
            task.status.message = Message(
                role="agent",
                message_id=str(uuid.uuid4()),
                parts=[TextPart(text=f"Error: {str(e)}")],
            )
            await event_queue.enqueue_event(task)

    async def cancel(self, context: RequestContext, event_queue: asyncio.Queue) -> None:
        """Cancel the task."""
        task = context.current_task
        if task:
            task.status.state = TaskState.canceled
            await event_queue.enqueue_event(task)


def create_agent_card(config: AgentConfig) -> AgentCard:
    """Create an AgentCard from configuration."""
    skills = [
        AgentSkill(
            id=skill["id"],
            name=skill["name"],
            description=skill["description"],
            tags=skill.get("tags", []),
        )
        for skill in config.skills
    ]

    return AgentCard(
        name=config.name,
        description=config.description,
        url=f"http://localhost:{config.port}",
        version=config.version,
        capabilities=AgentCapabilities(streaming=True, pushNotifications=False),
        skills=skills,
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
    )


def create_a2a_app(
    agent_config: AgentConfig,
    task_handler: Optional[Callable] = None,
) -> A2AStarletteApplication:
    """Create an A2A application for an agent."""
    agent_card = create_agent_card(agent_config)
    executor = BaseAgentExecutor(task_handler)
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    return A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )


async def run_agent_server(
    agent_config: AgentConfig,
    task_handler: Optional[Callable] = None,
) -> None:
    """Run an A2A agent server."""
    app = create_a2a_app(agent_config, task_handler)

    config = uvicorn.Config(
        app=app.build(),
        host="0.0.0.0",
        port=agent_config.port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
