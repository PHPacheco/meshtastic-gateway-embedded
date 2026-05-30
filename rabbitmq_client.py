import json
import os
import threading
import time
from datetime import datetime, timezone

import pika

from telegram_bot import load_env_file


RABBITMQ_HOST_ENV_VAR = "RABBITMQ_HOST"
RABBITMQ_PORT_ENV_VAR = "RABBITMQ_PORT"
RABBITMQ_USER_ENV_VAR = "RABBITMQ_USER"
RABBITMQ_PASSWORD_ENV_VAR = "RABBITMQ_PASSWORD"
RABBITMQ_EXCHANGE_ENV_VAR = "RABBITMQ_EXCHANGE"
RABBITMQ_TELEGRAM_QUEUE_ENV_VAR = "RABBITMQ_TELEGRAM_TO_MESHTASTIC_QUEUE"


class RabbitMQClient:
    def __init__(self):
        load_env_file()

        self.host = os.getenv(RABBITMQ_HOST_ENV_VAR, "localhost")
        self.port = int(os.getenv(RABBITMQ_PORT_ENV_VAR, "5672"))
        self.user = os.getenv(RABBITMQ_USER_ENV_VAR, "guest")
        self.password = os.getenv(RABBITMQ_PASSWORD_ENV_VAR, "guest")
        self.exchange = os.getenv(RABBITMQ_EXCHANGE_ENV_VAR, "mesh_gateway")
        self.telegram_to_meshtastic_queue = os.getenv(
            RABBITMQ_TELEGRAM_QUEUE_ENV_VAR,
            "telegram_to_meshtastic",
        )

        self.consumer_thread = None
        self.consumer_connection = None
        self.should_consume = False

    def connect(self):
        connection = None

        try:
            connection = self._create_connection()
            channel = connection.channel()
            self._setup_topology(channel)
            return True

        except Exception as error:
            print(f"RabbitMQ unavailable: {error}")
            return False

        finally:
            if connection and connection.is_open:
                connection.close()

    def publish_event(self, routing_key, payload):
        connection = None

        try:
            connection = self._create_connection()
            channel = connection.channel()
            self._setup_topology(channel)

            event = {
                "routing_key": routing_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }

            channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=json.dumps(event).encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
            )

        except Exception as error:
            print(f"RabbitMQ publish error: {error}")

        finally:
            if connection and connection.is_open:
                connection.close()

    def start_telegram_to_meshtastic_consumer(self, on_message):
        if self.consumer_thread and self.consumer_thread.is_alive():
            return

        self.should_consume = True
        self.consumer_thread = threading.Thread(
            target=self._consume_telegram_to_meshtastic,
            args=(on_message,),
            daemon=True,
        )
        self.consumer_thread.start()

    def _consume_telegram_to_meshtastic(self, on_message):
        while self.should_consume:
            try:
                self.consumer_connection = self._create_connection()
                channel = self.consumer_connection.channel()
                self._setup_topology(channel)

                for method, properties, body in channel.consume(
                    self.telegram_to_meshtastic_queue,
                    inactivity_timeout=1,
                ):
                    if not self.should_consume:
                        break

                    if method is None:
                        continue

                    try:
                        event = json.loads(body.decode("utf-8"))
                        payload = event.get("payload", event)
                        on_message(payload)
                        channel.basic_ack(method.delivery_tag)
                    except Exception as error:
                        print(f"RabbitMQ consumer error: {error}")
                        channel.basic_nack(method.delivery_tag, requeue=False)

            except Exception as error:
                print(f"RabbitMQ consume error: {error}")
                time.sleep(5)

            finally:
                self.close_consumer_connection()

    def _create_connection(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=30,
        )
        return pika.BlockingConnection(parameters)

    def _setup_topology(self, channel):
        channel.exchange_declare(
            exchange=self.exchange,
            exchange_type="topic",
            durable=True,
        )
        channel.queue_declare(
            queue=self.telegram_to_meshtastic_queue,
            durable=True,
        )
        channel.queue_bind(
            exchange=self.exchange,
            queue=self.telegram_to_meshtastic_queue,
            routing_key="gateway.command.telegram_to_meshtastic",
        )

    def close_consumer_connection(self):
        try:
            if self.consumer_connection and self.consumer_connection.is_open:
                self.consumer_connection.close()
        except Exception as error:
            print(f"RabbitMQ close error: {error}")
        finally:
            self.consumer_connection = None

    def stop(self):
        self.should_consume = False
        self.close_consumer_connection()
