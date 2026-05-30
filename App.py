import asyncio

from pubsub import pub

import BotDoTelegram
import ConexaoMeshtastic
from ChatIDs import ChatIDs
from NodesMeshtastic import NodesMeshtastic


class App:
    def __init__(self):
        self.loop = None
        self.telegram_app = None
        self.conexao = ConexaoMeshtastic.ConexaoMeshtastic(
            self.enviar_meshtastic_para_telegram
        )

    async def iniciar(self):
        self.loop = asyncio.get_running_loop()

        try:
            print("Iniciando bot do Telegram...")
            self.telegram_app = await BotDoTelegram.IniciarRecebimento(
                self.enviar_telegram_para_meshtastic
            )

            print("Iniciando sistema e assinando topicos Meshtastic...")
            pub.subscribe(self.conexao.ao_receber_pacote, "meshtastic.receive")

            print("Escutando Telegram e radio Meshtastic... (Ctrl+C para parar)")
            while True:
                await asyncio.sleep(1)

        finally:
            print("\nEncerrando...")

            if self.telegram_app:
                await BotDoTelegram.PararRecebimento(self.telegram_app)

            self.conexao.interface.close()

    def enviar_meshtastic_para_telegram(self, mensagem):
        if not self.loop:
            return

        asyncio.run_coroutine_threadsafe(
            BotDoTelegram.EnviarMensagem(ChatIDs.Amanda.value, mensagem),
            self.loop,
        )

    async def enviar_telegram_para_meshtastic(self, chat_id, mensagem):
        chat = self.obter_chat_cadastrado(chat_id)
        if not chat:
            print(f"Mensagem ignorada de chat nao cadastrado: {chat_id}")
            return

        node_destino = self.obter_node_destino(chat)
        if not node_destino:
            print(f"Node Meshtastic nao cadastrado para o chat {chat.name}")
            return

        self.conexao.enviar_mensagem_direta(node_destino, mensagem)
        print(f"[TELEGRAM -> MESHTASTIC] {chat.name} -> {node_destino}: {mensagem}")

    def obter_chat_cadastrado(self, chat_id):
        try:
            return ChatIDs(chat_id)
        except ValueError:
            return None

    def obter_node_destino(self, chat):
        try:
            node = NodesMeshtastic[chat.name].value
        except KeyError:
            return None

        if not node or node.startswith("cadastre_"):
            return None

        return node


if __name__ == "__main__":
    print("=" * 50)
    print("MeshMesh")
    print("=" * 50)

    app = App()

    try:
        asyncio.run(app.iniciar())
    except KeyboardInterrupt:
        pass
