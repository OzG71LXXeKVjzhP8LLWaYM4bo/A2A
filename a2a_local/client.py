"""A2A Client for inter-agent communication."""

import json
import time
import uuid
from typing import Any, Optional
from dataclasses import dataclass

import httpx
from a2a.client import A2AClient as BaseA2AClient
from a2a.types import AgentCard, Message, TextPart

from .logging_utils import log_agent_message, log_error


@dataclass
class AgentEndpoint:
    name: str
    url: str
    port: int

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"


class A2AClient:
    """Client for communicating with A2A agents."""

    def __init__(self, timeout: float = 120.0, caller_name: str = "Client"):
        self.timeout = timeout
        self.caller_name = caller_name
        self._http_client = httpx.AsyncClient(timeout=timeout)

    async def get_agent_card(self, endpoint: AgentEndpoint) -> Optional[AgentCard]:
        """Fetch agent card from an agent."""
        try:
            response = await self._http_client.get(
                f"{endpoint.base_url}/.well-known/agent.json"
            )
            response.raise_for_status()
            return AgentCard.model_validate(response.json())
        except Exception as e:
            log_error(self.caller_name, f"Failed to get agent card from {endpoint.name}: {e}")
            return None

    async def send_task(
        self,
        endpoint: AgentEndpoint,
        skill_id: str,
        message: str,
        params: Optional[dict] = None,
    ) -> dict:
        """Send a task to an agent and wait for completion."""
        # Parse message for logging
        try:
            message_data = json.loads(message)
        except json.JSONDecodeError:
            message_data = message

        # Log outgoing message
        log_agent_message(
            direction="SEND",
            from_agent=self.caller_name,
            to_agent=endpoint.name,
            message_type=skill_id,
            content=message_data,
            metadata=params,
        )

        start_time = time.time()

        try:
            # Create task message with required messageId
            task_message = Message(
                role="user",
                message_id=str(uuid.uuid4()),
                parts=[TextPart(text=message)],
            )

            # Send task via JSON-RPC
            payload = {
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": task_message.model_dump(),
                    "metadata": params or {},
                },
                "id": 1,
            }

            response = await self._http_client.post(
                f"{endpoint.base_url}/",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            elapsed_ms = (time.time() - start_time) * 1000

            if "error" in result:
                log_error(self.caller_name, f"Error from {endpoint.name}: {result['error']}")
                return {"error": result["error"]}

            # Log response
            response_data = result.get("result", {})
            log_agent_message(
                direction="RECEIVE",
                from_agent=endpoint.name,
                to_agent=self.caller_name,
                message_type=f"{skill_id}_response ({elapsed_ms:.0f}ms)",
                content=response_data,
            )

            return response_data

        except Exception as e:
            log_error(self.caller_name, f"Error sending to {endpoint.name}: {e}")
            return {"error": str(e)}

    async def send_task_streaming(
        self,
        endpoint: AgentEndpoint,
        skill_id: str,
        message: str,
        params: Optional[dict] = None,
    ):
        """Send a task and stream results."""
        try:
            task_message = Message(
                role="user",
                message_id=str(uuid.uuid4()),
                parts=[TextPart(text=message)],
            )

            payload = {
                "jsonrpc": "2.0",
                "method": "tasks/sendSubscribe",
                "params": {
                    "message": task_message.model_dump(),
                    "metadata": params or {},
                },
                "id": 1,
            }

            async with self._http_client.stream(
                "POST",
                f"{endpoint.base_url}/",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        yield data

        except Exception as e:
            yield {"error": str(e)}

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()


# Pre-configured agent endpoints
AGENT_ENDPOINTS = {
    # Core agents
    "orchestrator": AgentEndpoint("orchestrator", "http://localhost:5000", 5000),
    "image": AgentEndpoint("image", "http://localhost:5002", 5002),
    "database": AgentEndpoint("database", "http://localhost:5003", 5003),
    "math": AgentEndpoint("math", "http://localhost:5004", 5004),
    "reading": AgentEndpoint("reading", "http://localhost:5005", 5005),
    "verifier": AgentEndpoint("verifier", "http://localhost:5006", 5006),
    # Pipeline agents (consolidated)
    "concept_guide": AgentEndpoint("concept_guide", "http://localhost:5007", 5007),
    "question_generator": AgentEndpoint("question_generator", "http://localhost:5008", 5008),
    "quality_checker": AgentEndpoint("quality_checker", "http://localhost:5009", 5009),
}
