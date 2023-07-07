from queue import Queue
from typing import Callable

import asyncio_mqtt
from absl import logging

import garage_door_automation.contactsensor.mqtt as contact_sensor_mqtt
import garage_door_automation.motionsensor.mqtt as motion_sensor_mqtt
from garage_door_automation.mqtt.flag import (BROKER_ADDRESS, BROKER_PORT, CLIENT_ID, PASSWORD,
                                              USERNAME)


def create_mqtt_client() -> asyncio_mqtt.Client:
  return asyncio_mqtt.Client(
      hostname=str(BROKER_ADDRESS.value),
      port=int(BROKER_PORT.value),
      username=str(USERNAME.value),
      password=str(PASSWORD.value),
      client_id=str(CLIENT_ID.value),
      keepalive=10,
      clean_session=True,
  )


_MESSAGE_PROCESSORS: dict[str, Callable[[asyncio_mqtt.Message], list[str]]] = dict()


async def subscribe(client: asyncio_mqtt.Client) -> None:
  _MESSAGE_PROCESSORS.update(contact_sensor_mqtt.get_message_processors())
  _MESSAGE_PROCESSORS.update(motion_sensor_mqtt.get_message_processors())
  for topic in _MESSAGE_PROCESSORS.keys():
    await client.subscribe(topic)


async def process_message_loop(client: asyncio_mqtt.Client,
                               line_protocol_queue: Queue[str]) -> None:
  async with client.messages() as messages:
    async for message in messages:
      message_processor = _MESSAGE_PROCESSORS.get(message.topic.value)
      if message_processor is not None:
        try:
          line_protocols = message_processor(message)
        except Exception as e:
          e.add_note(f'Error when processing topic {message.topic}.')
          logging.exception(e)
          continue

        for lp in line_protocols:
          line_protocol_queue.put(lp)
        continue

      logging.error(f'No message processor for topic "{message.topic}".')
