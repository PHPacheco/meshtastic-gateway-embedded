import os

import meshtastic.serial_interface


MESHTASTIC_SERIAL_PORT_ENV_VAR = "MESHTASTIC_SERIAL_PORT"


class MeshtasticConnection:
    def __init__(self, on_message_received):
        serial_port = os.getenv(MESHTASTIC_SERIAL_PORT_ENV_VAR)
        if serial_port:
            self.interface = meshtastic.serial_interface.SerialInterface(
                devPath=serial_port
            )
        else:
            self.interface = meshtastic.serial_interface.SerialInterface()

        self.on_message_received = on_message_received
        self.received_messages = {}

    def send_direct_message(self, destination_node, message):
        if not destination_node or destination_node.startswith("register_"):
            raise ValueError("Destination Meshtastic node is not registered.")

        self.interface.sendText(message, destinationId=destination_node)

    def handle_received_packet(self, packet, interface):
        """Processes packets received from Meshtastic."""
        try:
            decoded = packet.get("decoded", {})
            if decoded.get("portnum") != "TEXT_MESSAGE_APP":
                return

            content = decoded.get("text", "")
            sender = packet.get("fromId", "unknown")

            self.received_messages[sender] = content

            print(f"\n[NEW MESHTASTIC MESSAGE] {sender}: {content}")
            print(f"Message map state: {self.received_messages}")

            self.on_message_received(sender, content)

        except Exception as error:
            print(f"Processing error: {error}")
