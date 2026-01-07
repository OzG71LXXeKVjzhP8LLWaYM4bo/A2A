"""Base agent class for all A2A agents."""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from google import genai
from google.genai.types import GenerateContentConfig

from a2a_local import AgentConfig, run_agent_server
from a2a_local.logging_utils import log_llm_call, log_error, log_info
from config import config


class BaseAgent(ABC):
    """Abstract base class for A2A agents."""

    def __init__(self, agent_config: AgentConfig):
        self.config = agent_config
        self._gemini_client: Optional[genai.Client] = None

    @property
    def agent_name(self) -> str:
        """Get the agent's display name."""
        return self.config.name

    @property
    def gemini_client(self) -> genai.Client:
        """Lazy initialization of Gemini client."""
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=config.gemini.api_key)
        return self._gemini_client

    @abstractmethod
    async def handle_task(self, task: Any, context: Any) -> dict:
        """Handle an incoming task. Must be implemented by subclasses."""
        pass

    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> str:
        """Generate content using Gemini."""
        model = model or config.gemini.flash_model
        model_short = model.split("/")[-1] if "/" in model else model

        start_time = time.time()

        try:
            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model=model,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # Log the LLM call
            log_llm_call(
                agent_name=self.agent_name,
                prompt=prompt,
                response=response.text,
                model=model_short,
                duration_ms=elapsed_ms,
            )

            return response.text

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            log_llm_call(
                agent_name=self.agent_name,
                prompt=prompt,
                model=model_short,
                error=str(e),
                duration_ms=elapsed_ms,
            )
            raise

    async def generate_json(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> list | dict:
        """Generate JSON content using Gemini."""
        response = await self.generate_content(
            prompt=prompt,
            model=model,
            temperature=temperature,
        )

        # Extract JSON from response
        text = response.strip()

        # Handle markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            log_error(self.agent_name, f"JSON parse error: {e}", context=text[:200])
            raise

    def load_prompt(self, *path_parts: str) -> str:
        """Load a prompt file from the prompts directory."""
        prompt_path = config.prompts_dir.joinpath(*path_parts)
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        return prompt_path.read_text()

    async def run(self):
        """Run the agent server."""
        log_info(self.agent_name, f"Starting on port {self.config.port}...")
        await run_agent_server(self.config, self.handle_task)
