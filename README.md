# Meshtastic Gateway Embedded

Python gateway for a Raspberry Pi that integrates Meshtastic, Telegram, a
hosted RabbitMQ broker, a FastAPI backend, and PostgreSQL.

## Current Architecture

```text
Meshtastic radio <-> Raspberry Pi gateway <-> Telegram
                           |
                           v
                    Hosted RabbitMQ
                           |
                           v
                  FastAPI backend -> PostgreSQL
```

The gateway keeps the real-time communication path simple: Telegram and
Meshtastic continue to work directly through the Raspberry service. RabbitMQ,
the backend, and PostgreSQL are used for message history, monitoring, and
backend-originated commands.

## Project Structure

```text
app.py                    Main gateway orchestrator
telegram_bot.py           Telegram bot integration
telegram_chats.py         Registered Telegram chats
meshtastic_connection.py  Meshtastic serial connection
meshtastic_nodes.py       Registered Meshtastic destination nodes
rabbitmq_client.py        RabbitMQ publisher and consumer
requirements.txt          Gateway Python dependencies
backend/                  FastAPI backend and PostgreSQL integration
ops/                      Raspberry service templates
```

## Gateway Environment

Copy `.env.example` to `.env` and fill in the values.

```env
TELEGRAM_BOT_TOKEN=your_token_here
MESHTASTIC_SERIAL_PORT=/dev/ttyUSB0
RABBITMQ_URL=amqps://user:password@host/vhost
RABBITMQ_EXCHANGE=mesh_gateway
RABBITMQ_TELEGRAM_TO_MESHTASTIC_QUEUE=telegram_to_meshtastic
```

If the hosted broker does not provide a single URL, keep `RABBITMQ_URL` empty
and fill `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`,
`RABBITMQ_PASSWORD`, and `RABBITMQ_USE_TLS`.

On Raspberry, the Meshtastic serial port is usually `/dev/ttyUSB0` or
`/dev/ttyACM0`. Check it with:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Register the real Meshtastic node in `meshtastic_nodes.py` before testing:

```python
Pedro = "!12345678"
```

## Run Gateway Natively on Raspberry

Recommended OS: Raspberry Pi OS 64-bit.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y ca-certificates curl git python3 python3-venv python3-pip

git clone https://github.com/PHPacheco/meshtastic-gateway-embedded.git
cd meshtastic-gateway-embedded

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env
python3 -m py_compile app.py telegram_bot.py telegram_chats.py meshtastic_connection.py meshtastic_nodes.py rabbitmq_client.py
python3 app.py
```

Expected result:

- Meshtastic text messages are forwarded to the registered Telegram chat.
- Telegram messages from registered chats are forwarded to the registered
  Meshtastic node.
- Gateway events are published to RabbitMQ.

## Run Gateway with systemd

Copy `ops/meshtastic-gateway.service` to `/etc/systemd/system/` and adjust
`WorkingDirectory`, `ExecStart`, and `User` if needed.

```bash
sudo cp ops/meshtastic-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable meshtastic-gateway
sudo systemctl start meshtastic-gateway
sudo systemctl status meshtastic-gateway
journalctl -u meshtastic-gateway -f
```

## RabbitMQ

Use a hosted broker such as CloudAMQP. The gateway publishes events to the
`mesh_gateway` topic exchange:

- `gateway.message.meshtastic_to_telegram`
- `gateway.message.telegram_to_meshtastic`

The gateway consumes backend commands from the `telegram_to_meshtastic` queue.
Commands use routing key `gateway.command.telegram_to_meshtastic`.

Command payload:

```json
{
  "payload": {
    "destination_node": "!12345678",
    "message": "Hello from backend"
  }
}
```

## Backend and PostgreSQL

The backend lives in `backend/`. It consumes gateway message events from
RabbitMQ, stores them in PostgreSQL, exposes read endpoints, and can publish
commands back to the gateway.

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

Backend endpoints:

- `GET /health`
- `GET /messages`
- `POST /messages`
- `GET /telegram-chats`
- `GET /meshtastic-nodes`
- `POST /commands/telegram-to-meshtastic`

Deploy the backend and PostgreSQL to a hosted platform such as Render or
Railway. Configure `DATABASE_URL` and the same RabbitMQ settings used by the
gateway.

## Final Validation Checklist

1. Gateway starts on Raspberry without Python errors.
2. Meshtastic device opens on `/dev/ttyUSB0` or `/dev/ttyACM0`.
3. Meshtastic -> Telegram works.
4. Telegram -> Meshtastic works.
5. RabbitMQ receives both gateway event types.
6. Backend `/health` returns `ok`.
7. PostgreSQL stores message history from RabbitMQ events.
8. `POST /commands/telegram-to-meshtastic` queues a command consumed by the
   gateway.
9. Prints/logs are captured for the final report.
