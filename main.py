"""Main entry point for running A2A agents."""

import asyncio
import sys

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

    elif agent_name == "image":
        from agents.image_agent import ImageAgent
        agent = ImageAgent()
        await agent.run()

    elif agent_name == "database":
        from agents.database_agent import DatabaseAgent
        agent = DatabaseAgent()
        await agent.run()

    elif agent_name == "verifier":
        from agents.verifier_agent import VerifierAgent
        agent = VerifierAgent()
        await agent.run()

    # Pipeline agents
    elif agent_name == "concept_guide":
        from agents.concept_guide_agent import ConceptGuideAgent
        agent = ConceptGuideAgent()
        await agent.run()

    elif agent_name == "question_generator":
        from agents.question_generator_agent import QuestionGeneratorAgent
        agent = QuestionGeneratorAgent()
        await agent.run()

    elif agent_name == "quality_checker":
        from agents.quality_checker_agent import QualityCheckerAgent
        agent = QualityCheckerAgent()
        await agent.run()

    elif agent_name == "correctness":
        from agents.correctness_agent import CorrectnessAgent
        agent = CorrectnessAgent()
        await agent.run()

    else:
        print(f"Unknown agent: {agent_name}")
        print("Core: orchestrator, image, database, verifier")
        print("Pipeline: concept_guide, question_generator, quality_checker, correctness")
        sys.exit(1)


async def run_all():
    """Run all agents concurrently."""
    print("Starting all agents...")
    print()
    print("Core agents:")
    print(f"  Orchestrator:         http://localhost:{config.ports.orchestrator}")
    print(f"  Image:                http://localhost:{config.ports.image}")
    print(f"  Database:             http://localhost:{config.ports.database}")
    print(f"  Verifier:             http://localhost:{config.ports.verifier}")
    print()
    print("Pipeline agents:")
    print(f"  Concept Guide:        http://localhost:{config.ports.concept_guide}")
    print(f"  Question Generator:   http://localhost:{config.ports.question_generator}")
    print(f"  Quality Checker:      http://localhost:{config.ports.quality_checker}")
    print(f"  Correctness:          http://localhost:{config.ports.correctness}")
    print()

    tasks = [
        run_agent("orchestrator"),
        run_agent("image"),
        run_agent("database"),
        run_agent("verifier"),
        run_agent("concept_guide"),
        run_agent("question_generator"),
        run_agent("quality_checker"),
        run_agent("correctness"),
    ]

    await asyncio.gather(*tasks)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <agent_name|all>")
        print()
        print("Core agents:")
        print(f"  orchestrator         - REST API + coordination (port {config.ports.orchestrator})")
        print(f"  image                - Diagram generation (port {config.ports.image})")
        print(f"  database             - PostgreSQL operations (port {config.ports.database})")
        print(f"  verifier             - Question verification (port {config.ports.verifier})")
        print()
        print("Pipeline agents:")
        print(f"  concept_guide        - Concept selection (port {config.ports.concept_guide})")
        print(f"  question_generator   - Blueprint + question (port {config.ports.question_generator})")
        print(f"  quality_checker      - Solve + attack + judge (port {config.ports.quality_checker})")
        print(f"  correctness          - Answer verification (port {config.ports.correctness})")
        print()
        print("  all                  - Run all 8 agents")
        sys.exit(1)

    agent_name = sys.argv[1].lower()

    if agent_name == "all":
        asyncio.run(run_all())
    else:
        asyncio.run(run_agent(agent_name))


if __name__ == "__main__":
    main()
