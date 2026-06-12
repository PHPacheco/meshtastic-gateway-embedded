import asyncio
import os

from pubsub import pub

import meshtastic_connection
import telegram_bot


TELEGRAM_CHAT_ID_ENV_VAR = "TELEGRAM_CHAT_ID"
MESHTASTIC_TARGET_NODE_ID_ENV_VAR = "MESHTASTIC_TARGET_NODE_ID"


class App:
    def __init__(self):
        self.loop = None
        self.telegram_chat_id = self.get_telegram_chat_id()
        self.meshtastic_target_node_id = self.get_meshtastic_target_node_id()
        self.telegram_listener_task = None
        self.meshtastic_connection = meshtastic_connection.MeshtasticConnection(
            self.forward_meshtastic_to_telegram
        )

    async def start(self):
        self.loop = asyncio.get_running_loop()

        try:
            print("Subscribing to Meshtastic topics...")
            pub.subscribe(
                self.meshtastic_connection.handle_received_packet,
                "meshtastic.receive",
            )

            self.telegram_listener_task = asyncio.create_task(
                telegram_bot.listen_for_messages(
                    self.telegram_chat_id,
                    self.forward_telegram_to_meshtastic,
                )
            )

            print(
                "Listening to Meshtastic radio and Telegram... (Ctrl+C to stop)"
            )
            while True:
                await asyncio.sleep(1)

        finally:
            print("\nShutting down...")
            if self.telegram_listener_task:
                self.telegram_listener_task.cancel()
                try:
                    await self.telegram_listener_task
                except asyncio.CancelledError:
                    pass
            self.meshtastic_connection.interface.close()

    def forward_meshtastic_to_telegram(self, sender_node, message):
        if not self.loop:
            return

        if sender_node != self.meshtastic_target_node_id:
            print(
                "[MESHTASTIC -> TELEGRAM SKIPPED] "
                f"{sender_node} is not {self.meshtastic_target_node_id}"
            )
            return

        telegram_message = f"{sender_node}: {message}"
        future = asyncio.run_coroutine_threadsafe(
            telegram_bot.send_message(self.telegram_chat_id, telegram_message),
            self.loop,
        )
        future.add_done_callback(self.log_telegram_send_error)
        print(f"[MESHTASTIC -> TELEGRAM] {telegram_message}")

    def log_telegram_send_error(self, future):
        try:
            future.result()
        except Exception as error:
            print(f"Telegram send failed: {error}")

    async def forward_telegram_to_meshtastic(self, message):
        try:
            self.meshtastic_connection.send_message(
                self.meshtastic_target_node_id,
                message,
            )
        except Exception as error:
            print(f"Meshtastic send failed: {error}")

    def get_telegram_chat_id(self):
        telegram_bot.load_env_file()
        chat_id = os.getenv(TELEGRAM_CHAT_ID_ENV_VAR)
        if not chat_id:
            raise RuntimeError(
                f"Configure the target chat in .env using {TELEGRAM_CHAT_ID_ENV_VAR}"
            )

        try:
            return int(chat_id)
        except ValueError as error:
            raise RuntimeError(
                f"{TELEGRAM_CHAT_ID_ENV_VAR} must be a Telegram numeric chat id."
            ) from error

    def get_meshtastic_target_node_id(self):
        telegram_bot.load_env_file()
        target_node_id = os.getenv(MESHTASTIC_TARGET_NODE_ID_ENV_VAR)
        if not target_node_id:
            raise RuntimeError(
                "Configure the Meshtastic target node in .env using "
                f"{MESHTASTIC_TARGET_NODE_ID_ENV_VAR}=!nodeid"
            )

        return target_node_id


if __name__ == "__main__":
    print("=" * 50)
    print("Meshtastic to Telegram Gateway")
    print("=" * 50)

    app = App()

    try:
        asyncio.run(app.start())
    except KeyboardInterrupt:
        pass
