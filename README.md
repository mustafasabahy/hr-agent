# HR Agent

Minimal Python 3.10+ proof of concept: one LangChain agent, one tool, local JSON,
and two API endpoints plus a simple chat page. All employee data is fictional.

## Run

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and replace OPENAI_API_KEY with your own key.
uvicorn main:app --reload
```

`OPENAI_MODEL` defaults to `gpt-4.1-mini` if unset. Chat requires a valid API key
and access to that model. Employee lookup works without an API key.

Open http://127.0.0.1:8000/ to use the chat UI. Press Enter to send; Shift+Enter adds a line.
The New chat button clears the visible conversation. Messages are not persisted
and previous questions are not sent to the model.

## Test

In another terminal:

```bash
curl http://127.0.0.1:8000/employees/Ahmed
curl -i http://127.0.0.1:8000/employees/Omar
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is Ahmed\u0027s department?"}'
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is Sara\u0027s role?"}'
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is Omar\u0027s department?"}'
```

Ahmed returns Engineering; Sara's role is HR Specialist. Omar is absent:
lookup returns HTTP 404 and chat should say the employee was not found.
Chat responses have the shape `{"answer": "..."}`. Without a configured key,
chat returns HTTP 503. Invalid request bodies return HTTP 422.

## How it works

`agent.py` defines a LangChain `ChatOpenAI` model, one `@tool` function named
`get_employee`, and the system prompt requiring tool use for employee data and
forbidding invented employee information. The model decides whether to call the
tool and extracts its name argument; there is no keyword routing.

`create_agent` builds the LangGraph execution loop: model → tools → model,
repeating as needed until the model gives a final answer. The single agent is
identified as `HR Agent` in the prompt, with internal graph name `HR_Agent`
(OpenAI message names cannot contain spaces), and initialized once on first use. No custom graph, memory,
checkpointing, or tracing is configured.

`GET /employees/{name}` uses the same `lookup_employee` function as the tool.
Names match exactly, ignoring case and surrounding spaces. `POST /chat` invokes
the agent with the user's message and returns its final text. Each request is
independent. FastAPI's documentation and schema routes are disabled.
