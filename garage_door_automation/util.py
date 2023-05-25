import json
from typing import Any

import asyncio_mqtt


def parse_payload(message: asyncio_mqtt.Message) -> dict[str, Any]:
  if not isinstance(message.payload, (str, bytes, bytearray)):
    raise ValueError('Expected message payload type to be str, bytes, or bytearray.')

  try:
    payload = json.loads(message.payload)
  except:
    raise ValueError('Unable to decode JSON payload.')

  if not isinstance(payload, dict):
    raise ValueError('Payload is not a dictionary.')

  for key in payload.keys():
    if not isinstance(key, str):
      raise ValueError(f'Payload key {key} is not a string.')

  return payload


def get_value(payload: dict[str, Any], key: str, expected_class: type):
  value = payload.get('contact')

  if value is None or not isinstance(value, expected_class):
    raise ValueError(f'Expected value type {expected_class} for key "{key}" but got {type(value)}.')

  return value
