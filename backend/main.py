import json
import os
import ssl
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import pika
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb


DATABASE_URL_ENV_VAR = "DATABASE_URL"
RABBITMQ_URL_ENV_VAR = "RABBITMQ_URL"
RABBITMQ_HOST_ENV_VAR = "RABBITMQ_HOST"
RABBITMQ_PORT_ENV_VAR = "RABBITMQ_PORT"
RABBITMQ_USER_ENV_VAR = "RABBITMQ_USER"
RABBITMQ_PASSWORD_ENV_VAR = "RABBITMQ_PASSWORD"
RABBITMQ_USE_TLS_ENV_VAR = "RABBITMQ_USE_TLS"
RABBITMQ_EXCHANGE_ENV_VAR = "RABBITMQ_EXCHANGE"
RABBITMQ_EVENTS_QUEUE_ENV_VAR = "RABBITMQ_EVENTS_QUEUE"
RABBITMQ_COMMAND_QUEUE_ENV_VAR = "RABBITMQ_TELEGRAM_TO_MESHTASTIC_QUEUE"


def load_env_file(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


class Settings:
    def __init__(self):
        self.database_url = self._required(DATABASE_URL_ENV_VAR)
        self.rabbitmq_url = os.getenv(RABBITMQ_URL_ENV_VAR)
        self.rabbitmq_host = os.getenv(RABBITMQ_HOST_ENV_VAR, "localhost")
        self.rabbitmq_port = int(os.getenv(RABBITMQ_PORT_ENV_VAR, "5672"))
        self.rabbitmq_user = os.getenv(RABBITMQ_USER_ENV_VAR, "guest")
        self.rabbitmq_password = os.getenv(RABBITMQ_PASSWORD_ENV_VAR, "guest")
        self.rabbitmq_use_tls = os.getenv(
            RABBITMQ_USE_TLS_ENV_VAR,
            "false",
        ).lower() in {"1", "true", "yes"}
        self.exchange = os.getenv(RABBITMQ_EXCHANGE_ENV_VAR, "mesh_gateway")
        self.events_queue = os.getenv(
            RABBITMQ_EVENTS_QUEUE_ENV_VAR,
            "gateway_events",
        )
        self.command_queue = os.getenv(
            RABBITMQ_COMMAND_QUEUE_ENV_VAR,
            "telegram_to_meshtastic",
        )

    def _required(self, name):
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Configure {name} before starting the backend.")
        return value


load_env_file()
settings = Settings()
app = FastAPI(title="Meshtastic Gateway Backend")
consumer = None


class CommandRequest(BaseModel):
    destination_node: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MessageRequest(BaseModel):
    direction: str = Field(min_length=1)
    source: str | None = None
    sender_id: str | None = None
    destination: str | None = None
    telegram_chat: str | None = None
    telegram_chat_id: int | None = None
    destination_node: str | None = None
    message: str = Field(min_length=1)


@contextmanager
def db_connection():
    with psycopg.connect(settings.database_url) as connection:
        yield connection


def create_rabbitmq_connection():
    if settings.rabbitmq_url:
        parameters = pika.URLParameters(settings.rabbitmq_url)
        parameters.heartbeat = 60
        parameters.blocked_connection_timeout = 30
        return pika.BlockingConnection(parameters)

    credentials = pika.PlainCredentials(
        settings.rabbitmq_user,
        settings.rabbitmq_password,
    )
    ssl_options = None
    if settings.rabbitmq_use_tls:
        ssl_options = pika.SSLOptions(ssl.create_default_context())

    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        credentials=credentials,
        ssl_options=ssl_options,
        heartbeat=60,
        blocked_connection_timeout=30,
    )
    return pika.BlockingConnection(parameters)


def setup_rabbitmq(channel):
    channel.exchange_declare(
        exchange=settings.exchange,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(queue=settings.events_queue, durable=True)
    channel.queue_bind(
        exchange=settings.exchange,
        queue=settings.events_queue,
        routing_key="gateway.message.*",
    )
    channel.queue_declare(queue=settings.command_queue, durable=True)
    channel.queue_bind(
        exchange=settings.exchange,
        queue=settings.command_queue,
        routing_key="gateway.command.telegram_to_meshtastic",
    )


def setup_database():
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    direction TEXT NOT NULL,
                    source TEXT,
                    sender_id TEXT,
                    destination TEXT,
                    telegram_chat TEXT,
                    telegram_chat_id BIGINT,
                    destination_node TEXT,
                    message TEXT NOT NULL,
                    event_routing_key TEXT,
                    event_timestamp TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_chats (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    telegram_chat_id BIGINT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS meshtastic_nodes (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    node_id TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gateway_events (
                    id BIGSERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    details JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        connection.commit()


def save_message(
    *,
    direction,
    source=None,
    sender_id=None,
    destination=None,
    telegram_chat=None,
    telegram_chat_id=None,
    destination_node=None,
    message,
    event_routing_key=None,
    event_timestamp=None,
):
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO messages (
                    direction, source, sender_id, destination, telegram_chat,
                    telegram_chat_id, destination_node, message,
                    event_routing_key, event_timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    direction,
                    source,
                    sender_id,
                    destination,
                    telegram_chat,
                    telegram_chat_id,
                    destination_node,
                    message,
                    event_routing_key,
                    event_timestamp,
                ),
            )
        connection.commit()


def save_gateway_event(event_type, details):
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO gateway_events (event_type, details)
                VALUES (%s, %s)
                """,
                (event_type, Jsonb(details)),
            )
        connection.commit()


def save_rabbitmq_event(event):
    routing_key = event.get("routing_key", "")
    payload = event.get("payload", {})
    event_timestamp = parse_timestamp(event.get("timestamp"))

    if routing_key.endswith("meshtastic_to_telegram"):
        save_message(
            direction="meshtastic_to_telegram",
            source="meshtastic",
            sender_id=payload.get("sender_node"),
            destination="telegram",
            telegram_chat=payload.get("telegram_chat"),
            telegram_chat_id=payload.get("telegram_chat_id"),
            message=payload.get("message", ""),
            event_routing_key=routing_key,
            event_timestamp=event_timestamp,
        )
        return

    if routing_key.endswith("telegram_to_meshtastic"):
        save_message(
            direction="telegram_to_meshtastic",
            source="telegram",
            destination="meshtastic",
            telegram_chat=payload.get("telegram_chat"),
            telegram_chat_id=payload.get("telegram_chat_id"),
            destination_node=payload.get("destination_node"),
            message=payload.get("message", ""),
            event_routing_key=routing_key,
            event_timestamp=event_timestamp,
        )
        return

    save_gateway_event("unknown_rabbitmq_event", event)


def parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class RabbitMQEventConsumer:
    def __init__(self):
        self.thread = None
        self.should_consume = False
        self.connection = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.should_consume = True
        self.thread = threading.Thread(target=self._consume, daemon=True)
        self.thread.start()

    def stop(self):
        self.should_consume = False
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception as error:
            print(f"RabbitMQ backend close error: {error}")

    def _consume(self):
        while self.should_consume:
            try:
                self.connection = create_rabbitmq_connection()
                channel = self.connection.channel()
                setup_rabbitmq(channel)

                for method, properties, body in channel.consume(
                    settings.events_queue,
                    inactivity_timeout=1,
                ):
                    if not self.should_consume:
                        break
                    if method is None:
                        continue
                    try:
                        event = json.loads(body.decode("utf-8"))
                        save_rabbitmq_event(event)
                        channel.basic_ack(method.delivery_tag)
                    except Exception as error:
                        print(f"RabbitMQ backend consumer error: {error}")
                        channel.basic_nack(method.delivery_tag, requeue=False)
            except Exception as error:
                print(f"RabbitMQ backend consume error: {error}")
                time.sleep(5)


@app.on_event("startup")
def on_startup():
    global consumer
    setup_database()
    consumer = RabbitMQEventConsumer()
    consumer.start()


@app.on_event("shutdown")
def on_shutdown():
    if consumer:
        consumer.stop()


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/messages")
def list_messages(limit: int = 50):
    limit = max(1, min(limit, 200))
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, direction, source, sender_id, destination,
                       telegram_chat, telegram_chat_id, destination_node,
                       message, event_routing_key, event_timestamp, created_at
                FROM messages
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "direction": row[1],
            "source": row[2],
            "sender_id": row[3],
            "destination": row[4],
            "telegram_chat": row[5],
            "telegram_chat_id": row[6],
            "destination_node": row[7],
            "message": row[8],
            "event_routing_key": row[9],
            "event_timestamp": row[10],
            "created_at": row[11],
        }
        for row in rows
    ]


@app.post("/messages", status_code=201)
def create_message(message: MessageRequest):
    save_message(**message.dict())
    return {"status": "created"}


@app.get("/telegram-chats")
def list_telegram_chats():
    return list_lookup_table("telegram_chats", "telegram_chat_id")


@app.get("/meshtastic-nodes")
def list_meshtastic_nodes():
    return list_lookup_table("meshtastic_nodes", "node_id")


@app.post("/commands/telegram-to-meshtastic", status_code=202)
def send_telegram_to_meshtastic_command(command: CommandRequest):
    event = {
        "routing_key": "gateway.command.telegram_to_meshtastic",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": command.dict(),
    }

    try:
        connection = create_rabbitmq_connection()
        channel = connection.channel()
        setup_rabbitmq(channel)
        channel.basic_publish(
            exchange=settings.exchange,
            routing_key=event["routing_key"],
            body=json.dumps(event).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
        )
        connection.close()
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {"status": "queued"}


def list_lookup_table(table_name, value_column):
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT name, {value_column}, created_at
                FROM {table_name}
                ORDER BY name
                """
            )
            rows = cursor.fetchall()

    return [
        {
            "name": row[0],
            value_column: row[1],
            "created_at": row[2],
        }
        for row in rows
    ]
