"""Local-only demo API. The application selects identity, never the LLM."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from agent import get_agent
from database import initialize, connect, today
from models import (
    ChatRequest,
    ChatResponse,
    OperationRequest,
    ConfirmationRequest,
    Result,
)
from services.common import (
    ACTOR,
    SCHEMAS,
    METADATA,
    execute,
    confirm,
    operation_details,
)
from tools.input_context import USER_MESSAGE


@asynccontextmanager
async def lifespan(app):
    initialize()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


async def identity(x_demo_user: str = Header(default="ahmed")):
    # This explicit test selector is intended ONLY for a loopback/local demo.
    # It is not authentication and must never be exposed as a production service.
    conn = connect()
    try:
        user = conn.execute(
            "SELECT id,employee_id,customer_id,roles FROM users WHERE id=?",
            (x_demo_user,),
        ).fetchone()
        if not user:
            raise HTTPException(401, "Unknown local demo user.")
        selected = dict(user)
    finally:
        conn.close()
    token = ACTOR.set(x_demo_user)
    try:
        yield selected
    finally:
        ACTOR.reset(token)


def http_result(result):
    if not result["ok"]:
        status = {
            "forbidden": 403,
            "unauthorized": 401,
            "not_found": 404,
            "conflict": 409,
        }.get(result.get("code"), 422)
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=status, content=Result(**result).model_dump())
    return result


@app.get("/", response_class=FileResponse)
def home():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/employees/{name}")
def employee(name: str, user=Depends(identity)):
    result = execute("get_employee", {"name": name})
    if not result["ok"]:
        raise HTTPException(
            {"not_found": 404, "forbidden": 403}.get(result.get("code"), 422),
            result["error"],
        )
    return result["data"]


@app.get("/demo/users")
def demo_users(user=Depends(identity)):
    conn = connect()
    try:
        return {
            "users": [
                dict(r)
                for r in conn.execute(
                    "SELECT id,employee_id,customer_id,roles FROM users"
                )
            ]
        }
    finally:
        conn.close()


@app.get("/operations")
def operations(user=Depends(identity)):
    return {"operations": {name: operation_details(name) for name in SCHEMAS}}


@app.post("/operations/{operation}", response_model=Result)
def business_operation(
    operation: str, request: OperationRequest, user=Depends(identity)
):
    return http_result(execute(operation, request.arguments))


@app.get("/confirmations/{confirmation_id}", response_model=Result)
def review_confirmation(confirmation_id: str, user=Depends(identity)):
    import json

    conn = connect()
    try:
        proposal = conn.execute(
            "SELECT id,operation,arguments,status,expires_at,result FROM confirmations WHERE id=? AND actor_id=?",
            (confirmation_id, user["id"]),
        ).fetchone()
        if not proposal:
            return http_result(
                {"ok": False, "code": "not_found", "error": "Confirmation not found."}
            )
        data = dict(proposal)
        data["arguments"] = json.loads(data["arguments"])
        data["result"] = json.loads(data["result"]) if data["result"] else None
        return {"ok": True, "data": data}
    finally:
        conn.close()


@app.post("/confirmations/{confirmation_id}", response_model=Result)
def confirmation(
    confirmation_id: str, request: ConfirmationRequest, user=Depends(identity)
):
    return http_result(confirm(confirmation_id, request.confirm))


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user=Depends(identity)):
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key == "your-openai-api-key":
        raise HTTPException(503, "Set OPENAI_API_KEY in .env to use chat.")
    # This application context is not inferred from the message or supplied as tool arguments.
    context = f"Trusted local demo context: user={user['id']}; employee_id={user['employee_id']}; customer_id={user['customer_id']}; roles={user['roles']}; company-local date={today()}."
    message_token = USER_MESSAGE.set(request.message)
    try:
        result = await run_in_threadpool(
            get_agent().invoke,
            {
                "messages": [
                    {"role": "system", "content": context},
                    {"role": "user", "content": request.message},
                ]
            },
        )
    except Exception:
        # Do not return provider errors, which can include credentials or request data.
        raise HTTPException(
            502, "Model request failed. Check model access and server configuration."
        )
    finally:
        USER_MESSAGE.reset(message_token)
    conn = connect()
    try:
        from database import utcnow

        pending = [
            {
                "confirmation_id": r["id"],
                "operation": r["operation"],
                "expires_at": r["expires_at"],
            }
            for r in conn.execute(
                "SELECT id,operation,expires_at FROM confirmations WHERE actor_id=? AND status='pending' AND expires_at>?",
                (user["id"], utcnow()),
            )
        ]
    finally:
        conn.close()
    return {"answer": result["messages"][-1].text, "confirmations": pending}
