# Meshtastic Gateway Embedded

Python gateway service that integrates Meshtastic, Telegram, and RabbitMQ.

## Current Features

- Meshtastic to Telegram message forwarding.
- Telegram to Meshtastic direct message forwarding.
- RabbitMQ event publishing for both message flows.
- RabbitMQ command consumer for backend-triggered Meshtastic messages.

## RabbitMQ

The project includes RabbitMQ with the Management UI through Docker Compose.

```powershell
docker compose up -d rabbitmq
```

RabbitMQ endpoints:

- AMQP broker: `localhost:5672`
- Management UI: `http://localhost:15672`
- Default user: `guest`
- Default password: `guest`

The gateway publishes events to the `mesh_gateway` topic exchange:

- `gateway.message.meshtastic_to_telegram`
- `gateway.message.telegram_to_meshtastic`

The gateway consumes backend commands from the `telegram_to_meshtastic` queue.
Commands can be published with routing key `gateway.command.telegram_to_meshtastic`
and payload:

```json
{
  "payload": {
    "destination_node": "!12345678",
    "message": "Hello from backend"
  }
}
```

## Environment

Copy `.env.example` to `.env` and fill in the values.

```env
TELEGRAM_BOT_TOKEN=your_token_here
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_EXCHANGE=mesh_gateway
RABBITMQ_TELEGRAM_TO_MESHTASTIC_QUEUE=telegram_to_meshtastic
```

## Next Architecture Steps

Backend/API should be a separate service, preferably using FastAPI. It should
expose HTTP endpoints to list messages, nodes, chats, and gateway health, and it
should publish commands to RabbitMQ when the user wants to send a Meshtastic
message through the gateway.

PostgreSQL should persist message history, node registry, Telegram chat registry,
delivery status, and logs. The Backend/API should be the main component reading
and writing PostgreSQL.

Cloud deployment should run RabbitMQ, PostgreSQL, Backend/API, and the gateway in
the same environment. A simple path is Docker Compose on a cloud VM. A more
managed path is to use a hosted PostgreSQL service, a hosted RabbitMQ service,
and deploy the API/gateway as containers.
