from json.decoder import JSONDecodeError
from typing import Callable

import asyncio_mqtt
import requests
from absl import logging

from garage_door_automation.motionsensor.datapoint import generate_data_point
from garage_door_automation.motionsensor.motionsensor import get_sensor, get_sensors
from garage_door_automation.util import get_bool, parse_payload


def _invoke_webhooks(message: asyncio_mqtt.Message) -> None:
  topic = message.topic.value
  try:
    sensor = get_sensor(topic)
  except ValueError as e:
    e.add_note(f'Unknown MQTT {topic=}.')
    logging.exception(e)
    return

  try:
    payload = parse_payload(message)
    is_occupied = get_bool(payload, 'occupancy')
  except (JSONDecodeError, AssertionError) as e:
    logging.exception(e)
    return

  webhook_url = sensor.occupancy_webhook if is_occupied else sensor.vacancy_webhook
  if webhook_url is None:
    return

  try:
    requests.get(webhook_url, timeout=10).raise_for_status()
  except Exception as e:
    e.add_note(f'Webhook invocation failed for sensor {sensor.nick_name}.')
    e.add_note(f'{is_occupied=}.')
    logging.exception(e)


def process_message(message: asyncio_mqtt.Message) -> list[str]:
  _invoke_webhooks(message)
  return generate_data_point(message)


def get_message_processors() -> dict[str, Callable[[asyncio_mqtt.Message], list[str]]]:
  return {s.mqtt_topic: process_message for s in get_sensors()}
