import meshtastic.serial_interface


class ConexaoMeshtastic:
    def __init__(self, ao_receber_mensagem):
        # Inicializa a interface fisica.
        self.interface = meshtastic.serial_interface.SerialInterface()
        self.ao_receber_mensagem = ao_receber_mensagem
        self.mensagens_recebidas = {}

    def enviar_mensagem_direta(self, node_destino, mensagem):
        if not node_destino or node_destino.startswith("cadastre_"):
            raise ValueError("Node Meshtastic de destino nao cadastrado.")

        self.interface.sendText(mensagem, destinationId=node_destino)

    def ao_receber_pacote(self, packet, interface):
        """Metodo que processa os dados recebidos."""
        try:
            decoded = packet.get("decoded", {})
            if decoded.get("portnum") != "TEXT_MESSAGE_APP":
                return

            conteudo = decoded.get("text", "")
            remetente = packet.get("fromId", "desconhecido")

            # Armazena a ultima mensagem recebida por remetente.
            self.mensagens_recebidas[remetente] = conteudo

            print(f"\n[NOVA MENSAGEM MESHTASTIC] {remetente}: {conteudo}")
            print(f"Estado do HashMap: {self.mensagens_recebidas}")

            self.ao_receber_mensagem(conteudo)

        except Exception as e:
            print(f"Erro no processamento: {e}")
