from json.decoder import JSONDecodeError
from typing import Callable

import asyncio_mqtt
import requests
from absl import logging

from garage_door_automation.contactsensor.contactsensor import get_sensor
from garage_door_automation.contactsensor.datapoint import generate_data_point
from garage_door_automation.contactsensor.position import Position
from garage_door_automation.util import get_bool, parse_payload


def _update_sensor(message: asyncio_mqtt.Message) -> None:
  topic = message.topic.value
  try:
    sensor = get_sensor(topic)
  except ValueError as e:
    e.add_note(f'Unknown MQTT {topic=}.')
    logging.exception(e)
    return

  try:
    payload = parse_payload(message)
    is_contact = get_bool(payload, 'contact')
  except (JSONDecodeError, AssertionError) as e:
    logging.exception(e)
    return

  sensor.set_is_contact(is_contact)


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
    is_contact = get_bool(payload, 'contact')
  except (JSONDecodeError, AssertionError) as e:
    logging.exception(e)
    return

  webhook_url = sensor.closed_webhook if is_contact else sensor.opened_webhook
  if webhook_url is None:
    return

  try:
    requests.get(webhook_url, timeout=10).raise_for_status()
  except Exception as e:
    e.add_note(f'Webhook invocation failed for sensor {sensor.nick_name}.')
    e.add_note(f'{is_contact=}.')
    logging.exception(e)


def process_message(message: asyncio_mqtt.Message) -> list[str]:
  _update_sensor(message)
  _invoke_webhooks(message)
  return generate_data_point(message)


def get_message_processors() -> dict[str, Callable[[asyncio_mqtt.Message], list[str]]]:
  return {get_sensor(p).mqtt_topic: process_message for p in Position}
