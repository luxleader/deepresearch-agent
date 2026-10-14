import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    provider: Literal["qwen", "compatible"] = "compatible"
    mode: Literal["replay", "live"] = "replay"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = Field(default="", repr=False)
    model: str = ""
    retriever: Literal["tavily"] = "tavily"
    database: str = "runtime/research.sqlite3"
    step_timeout: float = Field(default=180, gt=0, le=180)
    model_timeout: float = Field(default=60, gt=0, le=180)

    @classmethod
    def from_env(cls):
        load_dotenv(Path(".env"), override=False)
        return cls(
            provider=os.getenv("DR_PROVIDER", "compatible"),
            mode=os.getenv("DR_MODE", "replay"),
            api_base=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("DR_MODEL", ""),
            database=os.getenv("DR_DATABASE", "runtime/research.sqlite3"),
        )

    def validate_live(self):
        if not self.api_key or not self.model or not os.getenv("TAVILY_API_KEY"):
            raise ValueError("联网模式配置不完整：请在本机 .env 配置模型、模型密钥和 TAVILY_API_KEY")

    def llm_kwargs(self):
        return {"openai_api_base": self.api_base, "extra_body": {"enable_thinking": False}} if self.provider == "qwen" else {"openai_api_base": self.api_base}
