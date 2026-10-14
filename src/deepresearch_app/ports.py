from typing import Protocol, TypeVar

from pydantic import BaseModel

from .models import ResearchPacket, ResearchRequest

T = TypeVar("T", bound=BaseModel)


class ResearchBackend(Protocol):
    mode: str

    async def research(self, question: str, request: ResearchRequest) -> ResearchPacket: ...


class StructuredModel(Protocol):
    async def generate(self, prompt: str, schema: type[T]) -> T: ...
