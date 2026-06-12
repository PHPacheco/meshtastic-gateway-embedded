# Meshtastic Gateway Embedded

Python gateway service that forwards text messages from a Meshtastic node
connected through the computer serial port to a Telegram chat, and forwards
Telegram replies from the configured chat back to the configured Meshtastic
node.

## Architecture

```text
Meshtastic target node <-> Serial port <-> Gateway <-> Telegram chat
```

The service only forwards Meshtastic text messages received from the configured
target node. Telegram messages are only accepted from the configured chat id and
are sent back to the configured Meshtastic target node.

## Project Structure

```text
app.py                    Main gateway orchestrator
telegram_bot.py           Telegram bot integration
meshtastic_connection.py  Meshtastic serial connection
requirements.txt          Python dependencies
```

## Environment

The project includes a `.env` file with example values. Edit it before running
the gateway:

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=123456789
MESHTASTIC_SERIAL_PORT=/dev/ttyUSB0
MESHTASTIC_TARGET_NODE_ID=!0400c784
```

On Windows, the serial port usually looks like `COM3`, `COM4`, or another COM
port. On Linux or Raspberry, it is commonly `/dev/ttyUSB0` or `/dev/ttyACM0`.

If you are using a Heltec v3 as the node on Windows, install the Silicon Labs
CP210x driver first:

```text
https://www.silabs.com/documents/public/software/CP210x_Windows_Drivers.zip
```

On Linux or Raspberry, check the serial port with:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

## Running Locally

1. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

2. Edit the `.env` file and fill `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`MESHTASTIC_SERIAL_PORT`, and `MESHTASTIC_TARGET_NODE_ID`.

3. Validate Python syntax:

```powershell
python -m py_compile app.py telegram_bot.py meshtastic_connection.py
```

4. Start the gateway:

```powershell
python app.py
```

Expected result: sending a Meshtastic text message from
`MESHTASTIC_TARGET_NODE_ID` forwards it to the configured Telegram chat. Sending
a Telegram text message from `TELEGRAM_CHAT_ID` forwards it to
`MESHTASTIC_TARGET_NODE_ID`.

## Raspberry Pi Setup

Recommended OS: Raspberry Pi OS 64-bit.

1. Update the system:

```bash
sudo apt update
sudo apt upgrade -y
```

2. Install base packages:

```bash
sudo apt install -y ca-certificates curl git
```

3. Clone the project:

```bash
git clone https://github.com/PHPacheco/meshtastic-gateway-embedded.git
cd meshtastic-gateway-embedded
```

4. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

5. Edit `.env`:

```bash
nano .env
```

Set:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `MESHTASTIC_SERIAL_PORT`
- `MESHTASTIC_TARGET_NODE_ID`

6. Connect the Meshtastic device and check the serial port:

```bash
lsusb
ls /dev/ttyUSB* /dev/ttyACM*
```

If needed, use `/dev/ttyACM0` instead of `/dev/ttyUSB0` in `.env`.

7. Start the gateway:

```bash
python3 app.py
```

## Operational Checks

Check serial device permissions if the gateway cannot open Meshtastic:

```bash
ls -l /dev/ttyUSB0 /dev/ttyACM0
```

If the device path changes after reconnecting USB, update `MESHTASTIC_SERIAL_PORT`
in `.env` and restart `python3 app.py`.
