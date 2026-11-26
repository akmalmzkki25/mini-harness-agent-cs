# Mini Harness: Customer Service Agent

A compact customer-service agent for WhatsApp. Each incoming message is answered by a Gemini model that sees retrieved FAQ and product knowledge plus the conversation memory, and returns a structured decision: reply, hand off to a human, or escalate. The same agent can be driven from a local web chat page, so it can be tested without a WhatsApp Business setup.

## How it works

1. A message arrives through the WhatsApp Cloud API webhook (`routers/whatsapp.py`) or the web test chat (`routers/test_chat.py`).
2. `CustomerServiceAgent` loads conversation state from PostgreSQL and short-term memory and summaries from Redis.
3. The FAQ and product search tools query Typesense with keyword and vector search; embeddings come from the Gemini embedding API.
4. Gemini returns a structured decision (`reply`, `handoff`, `escalate`; `close` exists in the schema).
5. The reply is stored and sent back through WhatsApp or the web UI. A background scheduler processes handoffs that were not picked up by a human.

## Tech stack

Python 3.12, FastAPI, Uvicorn, SQLAlchemy (async) with PostgreSQL, Redis, Typesense, Google GenAI SDK (Gemini chat and embeddings), Pydantic settings, Docker.

## Structure

```
main.py                 app setup, runtime mode flags, health check
routers/                whatsapp.py (webhook), test_chat.py (web simulator)
app/services/           agent, conversation, memory, scheduler, WhatsApp services
app/tools/              FAQ and product search tools over Typesense
app/modules/            Gemini, Typesense, Redis and database adapters
app/commands/           Typesense collection setup and data indexing
app/data/               seed FAQ and product knowledge (JSON, Indonesian)
templates/test_chat.html  web chat page
docs/                   PRD and technical documentation
```

## Running locally

```bash
pip install -r requirements.txt
# configure DATABASE_URL, REDIS_URI, TYPESENSE_URI, TYPESENSE_API_KEY, GEMINI_API_KEY in .env
python -m app.commands.init_typesense
python -m app.commands.index_typesense_data
uvicorn main:app --reload
```

PostgreSQL, Redis and Typesense must be running; they are not started by the included `docker-compose.yml`, which only builds the app container. With `USE_WEBSITE=true` (the default) the web chat is served at `/test-chat`. Set `USE_WHATSAPP_WEBHOOK=true` and the WhatsApp credentials to enable the webhook at `/webhooks/whatsapp`. See `docs/DOCUMENTATION.md` for details and known limitations.
