"""Minimal FastAPI backend for the HR Agent."""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent import get_agent, lookup_employee

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/", response_class=FileResponse)
def home():
    return FileResponse(Path(__file__).with_name("index.html"))


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


@app.get("/employees/{name}")
def employee(name: str):
    result = lookup_employee(name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/chat")
def chat(request: ChatRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="Set OPENAI_API_KEY in .env to use chat.")
    result = get_agent().invoke(
        {"messages": [{"role": "user", "content": request.message}]}
    )
    return {"answer": result["messages"][-1].text}
