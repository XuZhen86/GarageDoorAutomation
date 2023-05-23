from queue import Queue
from typing import Callable

import asyncio_mqtt
from absl import flags, logging

import garage_door_automation.contactsensor as contact_sensor

_MQTT_CLIENT_ID = flags.DEFINE_string(
    name='mqtt_client_id',
    default='styrbar-to-elgato-key-light-air',
    help='The unique client id string used when connecting to the broker.',
)
_MQTT_USERNAME = flags.DEFINE_string(
    name='mqtt_username',
    default=None,
    required=True,
    help='The username to authenticate with. Need have no relationship to the client id.',
)
_MQTT_PASSWORD = flags.DEFINE_string(
    name='mqtt_password',
    default=None,
    required=True,
    help='The password to authenticate with. Optional, set to None if not required.',
)
_MQTT_BROKER_ADDRESS = flags.DEFINE_string(
    name='mqtt_broker_address',
    default=None,
    required=True,
    help='The hostname or IP address of the remote broker.',
)
_MQTT_BROKER_PORT = flags.DEFINE_integer(
    name='mqtt_broker_port',
    default=1883,
    help='The network port of the server host to connect to.',
)

MESSAGE_PROCESSORS: dict[str, Callable[[asyncio_mqtt.Message], None]] = dict()


def create_mqtt_client() -> asyncio_mqtt.Client:
  return asyncio_mqtt.Client(
      hostname=_MQTT_BROKER_ADDRESS.value,
      port=_MQTT_BROKER_PORT.value,
      username=_MQTT_USERNAME.value,
      password=_MQTT_PASSWORD.value,
      client_id=_MQTT_CLIENT_ID.value,
      keepalive=10,
      clean_session=True,
  )


async def subscribe(client: asyncio_mqtt.Client, line_protocol_queue: Queue[str]) -> None:
  MESSAGE_PROCESSORS.update(contact_sensor.get_message_processors(line_protocol_queue))
  for topic in MESSAGE_PROCESSORS.keys():
    await client.subscribe(topic)


def process_message(message: asyncio_mqtt.Message) -> None:
  if (message_processor := MESSAGE_PROCESSORS.get(
      message.topic.value)) and message_processor is not None:
    message_processor(message)
    return
  logging.error(f'No message processor for topic "{message.topic}".')


async def process_message_loop(client: asyncio_mqtt.Client) -> None:
  async with client.messages() as messages:
    async for message in messages:
      process_message(message)
