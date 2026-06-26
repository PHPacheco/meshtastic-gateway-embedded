# Meshtastic Gateway Backend

FastAPI service that stores gateway events in PostgreSQL and publishes commands
back to the Raspberry gateway through RabbitMQ.

## Environment

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL`: hosted PostgreSQL connection string.
- `RABBITMQ_URL`: hosted RabbitMQ URL, preferably `amqps://...`.
- `RABBITMQ_EXCHANGE`: keep `mesh_gateway` unless the gateway uses another name.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API

- `GET /health`
- `GET /messages`
- `POST /messages`
- `GET /telegram-chats`
- `GET /meshtastic-nodes`
- `POST /commands/telegram-to-meshtastic`

Command payload:

```json
{
  "destination_node": "!12345678",
  "message": "Hello from backend"
}
```
