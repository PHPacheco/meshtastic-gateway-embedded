import inspect
import os

from telegram import Bot
from telegram.ext import ApplicationBuilder, MessageHandler, filters


TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"


def carregar_env(caminho=".env"):
    """Carrega variaveis simples de um arquivo .env sem depender de pacotes."""
    if not os.path.exists(caminho):
        return

    with open(caminho, "r", encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()

            if not linha or linha.startswith("#") or "=" not in linha:
                continue

            chave, valor = linha.split("=", 1)
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")

            if chave and chave not in os.environ:
                os.environ[chave] = valor


def obter_token():
    carregar_env()
    token = os.getenv(TOKEN_ENV_VAR)

    if not token or token == "coloque_seu_token_aqui":
        raise RuntimeError(
            f"Configure o token do bot no arquivo .env usando {TOKEN_ENV_VAR}=seu_token"
        )

    return token


async def EnviarMensagem(chatID, mensagem):
    if not mensagem:
        print(f"Erro: mensagem vazia para o chat {chatID}")
        return

    bot = Bot(token=obter_token())
    await bot.send_message(chatID, text=mensagem)


async def IniciarRecebimento(ao_receber_mensagem):
    app = ApplicationBuilder().token(obter_token()).build()

    async def tratar_mensagem(update, context):
        if not update.effective_chat or not update.message or not update.message.text:
            return

        resultado = ao_receber_mensagem(
            update.effective_chat.id,
            update.message.text,
        )

        if inspect.isawaitable(resultado):
            await resultado

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tratar_mensagem))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    return app


async def PararRecebimento(app):
    if app.updater:
        await app.updater.stop()

    await app.stop()
    await app.shutdown()
