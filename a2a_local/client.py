"""A2A Client for inter-agent communication."""

import json
from typing import Any, Optional
from dataclasses import dataclass

import httpx
from a2a.client import A2AClient as BaseA2AClient
from a2a.types import AgentCard, Message, TextPart


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

    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
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
            print(f"Failed to get agent card from {endpoint.name}: {e}")
            return None

    async def send_task(
        self,
        endpoint: AgentEndpoint,
        skill_id: str,
        message: str,
        params: Optional[dict] = None,
    ) -> dict:
        """Send a task to an agent and wait for completion."""
        try:
            # Create task message
            task_message = Message(
                role="user",
                parts=[TextPart(text=message)],
            )

            # Send task via JSON-RPC
            payload = {
                "jsonrpc": "2.0",
                "method": "tasks/send",
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

            if "error" in result:
                return {"error": result["error"]}

            return result.get("result", {})

        except Exception as e:
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
    "orchestrator": AgentEndpoint("orchestrator", "http://localhost:5000", 5000),
    "thinking_skills": AgentEndpoint("thinking_skills", "http://localhost:5001", 5001),
    "image": AgentEndpoint("image", "http://localhost:5002", 5002),
    "database": AgentEndpoint("database", "http://localhost:5003", 5003),
    "math": AgentEndpoint("math", "http://localhost:5004", 5004),
    "reading": AgentEndpoint("reading", "http://localhost:5005", 5005),
}
