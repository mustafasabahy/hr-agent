"""Shared request/response schemas. Operation-specific schemas come from signatures."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=8000)


class OperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirm: bool


class Result(BaseModel):
    ok: bool
    data: Any = None
    error: str | None = None
    code: str | None = None
    operation: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    clarification_required: bool = False
    next_step: str | None = None
    trusted_context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    confirmations: list[dict[str, Any]] = Field(default_factory=list)
