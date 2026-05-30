import inspect
import os

from telegram import Bot
from telegram.ext import ApplicationBuilder, MessageHandler, filters


TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"
TOKEN_PLACEHOLDERS = {"coloque_seu_token_aqui", "your_token_here"}


def load_env_file(path=".env"):
    """Loads simple environment variables from a .env file."""
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


def get_token():
    load_env_file()
    token = os.getenv(TOKEN_ENV_VAR)

    if not token or token in TOKEN_PLACEHOLDERS:
        raise RuntimeError(
            f"Configure the bot token in .env using {TOKEN_ENV_VAR}=your_token"
        )

    return token


async def send_message(chat_id, message):
    if not message:
        print(f"Error: empty message for chat {chat_id}")
        return

    bot = Bot(token=get_token())
    await bot.send_message(chat_id, text=message)


async def start_message_listener(on_message_received):
    app = ApplicationBuilder().token(get_token()).build()

    async def handle_message(update, context):
        if not update.effective_chat or not update.message or not update.message.text:
            return

        result = on_message_received(
            update.effective_chat.id,
            update.message.text,
        )

        if inspect.isawaitable(result):
            await result

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    return app


async def stop_message_listener(app):
    if app.updater:
        await app.updater.stop()

    await app.stop()
    await app.shutdown()
