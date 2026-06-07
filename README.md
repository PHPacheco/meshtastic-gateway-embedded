# Meshtastic Gateway Embedded

Python gateway service for a Raspberry Pi that integrates Meshtastic, Telegram,
and RabbitMQ.

## Current Architecture

```text
Telegram <-> Gateway container <-> Meshtastic radio
                 |
                 v
            RabbitMQ container
```

The Raspberry Pi runs:

- `gateway`: Python service responsible for Telegram, Meshtastic, and RabbitMQ.
- `rabbitmq`: message broker with the Management UI enabled.

The cloud backend/API and PostgreSQL database will be added later as separate
cloud services.

## Project Structure

```text
app.py                    Main gateway orchestrator
telegram_bot.py           Telegram bot integration
telegram_chats.py         Registered Telegram chats
meshtastic_connection.py  Meshtastic serial connection
meshtastic_nodes.py       Registered Meshtastic destination nodes
rabbitmq_client.py        RabbitMQ publisher and consumer
Dockerfile                Gateway container image
docker-compose.yml        Raspberry services: gateway + RabbitMQ
requirements.txt          Python dependencies
```

## Environment

Copy `.env.example` to `.env` and fill in the values.

```env
TELEGRAM_BOT_TOKEN=your_token_here
MESHTASTIC_SERIAL_PORT=/dev/ttyUSB0
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_EXCHANGE=mesh_gateway
RABBITMQ_TELEGRAM_TO_MESHTASTIC_QUEUE=telegram_to_meshtastic
```

On Raspberry, the serial port can also be `/dev/ttyACM0`. Check it with:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

## RabbitMQ

RabbitMQ runs with the Management UI through Docker Compose.

```bash
docker compose up -d rabbitmq
```

Endpoints:

- AMQP broker: `localhost:5672`
- Management UI: `http://<raspberry-ip>:15672`
- Default user: `guest`
- Default password: `guest`

The gateway publishes events to the `mesh_gateway` topic exchange:

- `gateway.message.meshtastic_to_telegram`
- `gateway.message.telegram_to_meshtastic`

The gateway consumes backend commands from the `telegram_to_meshtastic` queue.
Commands can be published with routing key `gateway.command.telegram_to_meshtastic`.

Payload example:

```json
{
  "payload": {
    "destination_node": "!12345678",
    "message": "Hello from backend"
  }
}
```

## Tests Before Raspberry Deployment

Run these tests on your development machine before moving the project to the
Raspberry.

1. Validate Python syntax:

```powershell
python -m py_compile app.py telegram_bot.py telegram_chats.py meshtastic_connection.py meshtastic_nodes.py rabbitmq_client.py
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. Validate environment file:

```powershell
Copy-Item .env.example .env
```

Then fill `TELEGRAM_BOT_TOKEN` and keep `.env` out of Git.

4. Validate RabbitMQ with Docker:

```powershell
docker compose up -d rabbitmq
docker compose ps
```

Open `http://localhost:15672` and log in with the configured user/password.

5. Validate gateway container build:

```powershell
docker compose build gateway
```

6. Validate full stack without Meshtastic connected:

```powershell
docker compose up gateway rabbitmq
```

Expected result: RabbitMQ starts, and the gateway may fail only at the
Meshtastic serial connection if no device is connected. RabbitMQ errors should
not appear once the broker is healthy.

7. Validate with Meshtastic connected:

```powershell
docker compose up
```

Expected result:

- Sending a Meshtastic text message forwards it to Telegram.
- Sending a Telegram message from a registered chat forwards it to the
  registered Meshtastic node.
- RabbitMQ Management UI shows the `mesh_gateway` exchange and
  `telegram_to_meshtastic` queue.

## Raspberry Pi Setup

Recommended OS: Raspberry Pi OS 64-bit, based on Debian.

1. Update the Raspberry:

```bash
sudo apt update
sudo apt upgrade -y
```

2. Install base packages:

```bash
sudo apt install -y ca-certificates curl git
```

3. Install Docker using Docker's official Debian/Raspberry Pi OS instructions.
For Raspberry Pi OS 64-bit, the Debian install path is commonly used:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

4. Allow your user to run Docker:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

5. Validate Docker:

```bash
docker --version
docker compose version
docker run hello-world
```

6. Clone the project:

```bash
git clone https://github.com/PHPacheco/meshtastic-gateway-embedded.git
cd meshtastic-gateway-embedded
```

7. Create `.env`:

```bash
cp .env.example .env
nano .env
```

Set:

- `TELEGRAM_BOT_TOKEN`
- `MESHTASTIC_SERIAL_PORT`
- RabbitMQ credentials, if changed.

8. Connect the Meshtastic device and check the serial port:

```bash
lsusb
ls /dev/ttyUSB* /dev/ttyACM*
```

If needed, use `/dev/ttyACM0` instead of `/dev/ttyUSB0` in `.env`.

9. Start RabbitMQ first:

```bash
docker compose up -d rabbitmq
docker compose logs -f rabbitmq
```

10. Open the Management UI:

```text
http://<raspberry-ip>:15672
```

11. Start the gateway:

```bash
docker compose up -d gateway
docker compose logs -f gateway
```

12. Start everything automatically after reboot:

The compose services already use `restart: unless-stopped`. After Docker starts,
the containers will restart automatically unless stopped manually.

## Operational Checks on Raspberry

```bash
docker compose ps
docker compose logs -f gateway
docker compose logs -f rabbitmq
```

Check serial device permissions if the gateway cannot open Meshtastic:

```bash
ls -l /dev/ttyUSB0 /dev/ttyACM0
```

If the device path changes after reconnecting USB, update `MESHTASTIC_SERIAL_PORT`
in `.env` and restart:

```bash
docker compose down
docker compose up -d
```

## Notes for Backend/API, PostgreSQL, and Cloud

The Backend/API should run in the cloud and expose endpoints to:

- List messages.
- List Telegram chats.
- List Meshtastic nodes.
- Check gateway health.
- Send message commands through RabbitMQ.

PostgreSQL should also run in the cloud and store:

- Message history.
- Registered nodes.
- Registered Telegram chats.
- Delivery status.
- Gateway logs and health events.

Cloud integration options:

- Keep RabbitMQ on the Raspberry for local tests.
- Move RabbitMQ to the cloud later so both the gateway and API connect outward to
  the same broker. This is usually easier and safer than exposing the Raspberry
  RabbitMQ port to the public internet.
