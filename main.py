"""Main entry point for running A2A agents."""

import asyncio
import sys
from typing import Optional

import uvicorn

from config import config


async def run_agent(agent_name: str):
    """Run a specific agent."""
    if agent_name == "orchestrator":
        from agents.orchestrator import create_api_app
        app = create_api_app()
        uvicorn_config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=config.ports.orchestrator,
            log_level="info",
        )
        server = uvicorn.Server(uvicorn_config)
        await server.serve()

    elif agent_name == "thinking_skills":
        from agents.thinking_skills_agent import ThinkingSkillsAgent
        agent = ThinkingSkillsAgent()
        await agent.run()

    elif agent_name == "image":
        from agents.image_agent import ImageAgent
        agent = ImageAgent()
        await agent.run()

    elif agent_name == "database":
        from agents.database_agent import DatabaseAgent
        agent = DatabaseAgent()
        await agent.run()

    else:
        print(f"Unknown agent: {agent_name}")
        print("Available agents: orchestrator, thinking_skills, image, database")
        sys.exit(1)


async def run_all():
    """Run all agents concurrently."""
    print("Starting all agents...")
    print(f"  Orchestrator:      http://localhost:{config.ports.orchestrator}")
    print(f"  Thinking Skills:   http://localhost:{config.ports.thinking_skills}")
    print(f"  Image:             http://localhost:{config.ports.image}")
    print(f"  Database:          http://localhost:{config.ports.database}")
    print()

    tasks = [
        run_agent("orchestrator"),
        run_agent("thinking_skills"),
        run_agent("image"),
        run_agent("database"),
    ]

    await asyncio.gather(*tasks)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <agent_name|all>")
        print()
        print("Available agents:")
        print("  orchestrator     - Main orchestrator with REST API (port 5000)")
        print("  thinking_skills  - Thinking Skills question generator (port 5001)")
        print("  image            - Image/diagram generator (port 5002)")
        print("  database         - PostgreSQL database operations (port 5003)")
        print("  all              - Run all agents concurrently")
        sys.exit(1)

    agent_name = sys.argv[1].lower()

    if agent_name == "all":
        asyncio.run(run_all())
    else:
        asyncio.run(run_agent(agent_name))


if __name__ == "__main__":
    main()
