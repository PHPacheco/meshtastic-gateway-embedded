import asyncio

from pubsub import pub

import meshtastic_connection
import rabbitmq_client
import telegram_bot
from meshtastic_nodes import MeshtasticNodes
from telegram_chats import TelegramChats


class App:
    def __init__(self):
        self.loop = None
        self.telegram_app = None
        self.rabbitmq = rabbitmq_client.RabbitMQClient()
        self.meshtastic_connection = meshtastic_connection.MeshtasticConnection(
            self.forward_meshtastic_to_telegram
        )

    async def start(self):
        self.loop = asyncio.get_running_loop()

        try:
            print("Starting Telegram bot...")
            self.telegram_app = await telegram_bot.start_message_listener(
                self.forward_telegram_to_meshtastic
            )

            print("Starting RabbitMQ integration...")
            self.rabbitmq.connect()
            self.rabbitmq.start_telegram_to_meshtastic_consumer(
                self.forward_rabbitmq_to_meshtastic
            )

            print("Subscribing to Meshtastic topics...")
            pub.subscribe(
                self.meshtastic_connection.handle_received_packet,
                "meshtastic.receive",
            )

            print("Listening to Telegram and Meshtastic radio... (Ctrl+C to stop)")
            while True:
                await asyncio.sleep(1)

        finally:
            print("\nShutting down...")

            if self.telegram_app:
                await telegram_bot.stop_message_listener(self.telegram_app)

            self.rabbitmq.stop()
            self.meshtastic_connection.interface.close()

    def forward_meshtastic_to_telegram(self, sender_node, message):
        if not self.loop:
            return

        self.rabbitmq.publish_event(
            "gateway.message.meshtastic_to_telegram",
            {
                "sender_node": sender_node,
                "telegram_chat": TelegramChats.Pedro.name,
                "telegram_chat_id": TelegramChats.Pedro.value,
                "message": message,
            },
        )

        asyncio.run_coroutine_threadsafe(
            telegram_bot.send_message(TelegramChats.Pedro.value, message),
            self.loop,
        )

    async def forward_telegram_to_meshtastic(self, chat_id, message):
        chat = self.get_registered_chat(chat_id)
        if not chat:
            print(f"Ignoring message from unregistered chat: {chat_id}")
            return

        destination_node = self.get_destination_node(chat)
        if not destination_node:
            print(f"Meshtastic node is not registered for chat {chat.name}")
            return

        self.meshtastic_connection.send_direct_message(destination_node, message)
        self.rabbitmq.publish_event(
            "gateway.message.telegram_to_meshtastic",
            {
                "telegram_chat": chat.name,
                "telegram_chat_id": chat_id,
                "destination_node": destination_node,
                "message": message,
            },
        )
        print(f"[TELEGRAM -> MESHTASTIC] {chat.name} -> {destination_node}: {message}")

    def forward_rabbitmq_to_meshtastic(self, payload):
        destination_node = payload.get("destination_node")
        message = payload.get("message")

        if not destination_node or not message:
            print(f"Ignoring invalid RabbitMQ command: {payload}")
            return

        self.meshtastic_connection.send_direct_message(destination_node, message)
        print(f"[RABBITMQ -> MESHTASTIC] {destination_node}: {message}")

    def get_registered_chat(self, chat_id):
        try:
            return TelegramChats(chat_id)
        except ValueError:
            return None

    def get_destination_node(self, chat):
        try:
            node = MeshtasticNodes[chat.name].value
        except KeyError:
            return None

        if not node or node.startswith("register_"):
            return None

        return node


if __name__ == "__main__":
    print("=" * 50)
    print("Meshtastic Gateway Embedded")
    print("=" * 50)

    app = App()

    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        pass
