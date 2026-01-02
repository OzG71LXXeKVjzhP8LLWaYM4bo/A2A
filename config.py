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
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class GeminiConfig(BaseModel):
    api_key: str = os.getenv("GEMINI_API_KEY", "")
    flash_model: str = "gemini-2.0-flash"
    pro_model: str = "gemini-3-pro-preview"
    image_model: str = "gemini-3-pro-image-preview"


class AgentPorts(BaseModel):
    orchestrator: int = 5000
    thinking_skills: int = 5001
    image: int = 5002
    database: int = 5003
    math: int = 5004
    reading: int = 5005
    verifier: int = 5006


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

    # Topic UUIDs from n8n workflow
    topic_uuids: dict = {
        "reading": "8e64a8a1-126a-41d4-a8a1-40116970e9bc",
        "mathematics": "64cc2488-91f0-43e3-a560-b2bccf91442c",
        "thinking_skills": "096feb43-20f5-4ab7-8e3f-feb907884f9e",
        "writing": "f2a2bd14-b5bc-424c-990a-1f60d55cb506",
    }


config = Config()
