"""Configuration management for A2A agents."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class DatabaseConfig(BaseModel):
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    name: str = os.getenv("DB_NAME", "selective")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "")

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}?sslmode=require"


class GeminiConfig(BaseModel):
    api_key: str = os.getenv("GEMINI_API_KEY", "")
    # Use Gemini 2.0 Flash for fast text generation
    flash_model: str = "gemini-2.0-flash"
    # Use Gemini 2.5 Pro for complex reasoning
    pro_model: str = "gemini-2.5-pro-preview-06-05"
    # Use Imagen 3 for image generation
    image_model: str = "imagen-3.0-generate-002"


class AgentPorts(BaseModel):
    orchestrator: int = 5000
    image: int = 5002
    database: int = 5003
    math: int = 5004
    reading: int = 5005
    verifier: int = 5006
    # Pipeline agents (consolidated)
    concept_guide: int = 5007
    question_generator: int = 5008  # Merged: planner + realiser
    quality_checker: int = 5009     # Merged: solver + adversarial + judge


class R2Config(BaseModel):
    account_id: str = os.getenv("R2_ACCOUNT_ID", "")
    bucket_name: str = os.getenv("R2_BUCKET_NAME", "")
    access_key: str = os.getenv("R2_ACCESS_KEY", "")
    secret_key: str = os.getenv("R2_SECRET_KEY", "")
    public_url: str = os.getenv("R2_PUBLIC_URL", "")


class Config(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    gemini: GeminiConfig = GeminiConfig()
    ports: AgentPorts = AgentPorts()
    r2: R2Config = R2Config()
    prompts_dir: Path = Path(__file__).parent / "prompts"
    data_dir: Path = Path(__file__).parent / "data"

    # Topic UUIDs from database
    topic_uuids: dict = {
        "reading": "8e64a8a1-126a-41d4-a8a1-40116970e9bc",
        "mathematics": "64cc2488-91f0-43e3-a560-b2bccf91442c",
        "thinking_skills": "096feb43-20f5-4ab7-8e3f-feb907884f9e",
        "writing": "f2a2bd14-b5bc-424c-990a-1f60d55cb506",
    }

    # Thinking Skills subtopic UUIDs from database
    thinking_skills_subtopics: dict = {
        "analogies": {
            "id": "fb7782d6-b227-48eb-a010-a6ea21c3e8df",
            "name": "Analogies",
            "display_name": "Conditional Logic",
        },
        "critical_thinking": {
            "id": "b131ca12-b369-4823-a459-a389064dc7bf",
            "name": "Critical Thinking",
            "display_name": "Critical Thinking",
        },
        "deduction": {
            "id": "81762f7f-019e-4834-a764-fc4a830a46db",
            "name": "Deduction",
            "display_name": "Deduction",
        },
        "inference": {
            "id": "1b4015b7-8647-4229-afd2-0717ed2786ee",
            "name": "Inference",
            "display_name": "Inference",
        },
        "logical_reasoning": {
            "id": "01915e09-31a5-4757-b666-0a3a8811b663",
            "name": "Logical Reasoning",
            "display_name": "Logical Reasoning",
        },
        "pattern_recognition": {
            "id": "98d8d204-fd1e-431e-b689-f8198235a6bc",
            "name": "Pattern Recognition",
            "display_name": "Pattern Recognition",
        },
        "numerical_reasoning": {
            "id": "40825bd0-994a-4e6e-8417-03aa359b45c6",
            "name": "Numerical Reasoning",
            "display_name": "Numerical Reasoning",
        },
        "spatial_reasoning": {
            "id": "2c6553b7-29cd-4f4e-8291-4ee25921f8e0",
            "name": "Spatial Reasoning",
            "display_name": "Spatial Reasoning",
        },
    }

    # Mathematics subtopic UUIDs (NSW Selective exam - 35 questions, 40 minutes)
    math_subtopics: dict = {
        "geometry": {
            "id": "a1b2c3d4-1111-4000-8000-000000000001",
            "name": "Geometry",
            "display_name": "Geometry",
        },
        "number_operations": {
            "id": "a1b2c3d4-2222-4000-8000-000000000002",
            "name": "Number Operations",
            "display_name": "Number Operations",
        },
        "measurement": {
            "id": "a1b2c3d4-3333-4000-8000-000000000003",
            "name": "Measurement",
            "display_name": "Measurement",
        },
        "algebra_patterns": {
            "id": "a1b2c3d4-4444-4000-8000-000000000004",
            "name": "Algebra & Patterns",
            "display_name": "Algebra & Patterns",
        },
        "fractions_decimals": {
            "id": "a1b2c3d4-5555-4000-8000-000000000005",
            "name": "Fractions & Decimals",
            "display_name": "Fractions & Decimals",
        },
        "probability": {
            "id": "a1b2c3d4-6666-4000-8000-000000000006",
            "name": "Probability",
            "display_name": "Probability",
        },
        "data_statistics": {
            "id": "a1b2c3d4-7777-4000-8000-000000000007",
            "name": "Data & Statistics",
            "display_name": "Data & Statistics",
        },
        "number_theory": {
            "id": "a1b2c3d4-8888-4000-8000-000000000008",
            "name": "Number Theory",
            "display_name": "Number Theory",
        },
    }

    # Pipeline configuration
    max_pipeline_retries: int = 3
    min_quality_threshold: float = 0.7
    min_solver_confidence: float = 0.9
    min_adversarial_robustness: float = 0.7


config = Config()
