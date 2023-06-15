import json
from typing import Any

import asyncio_mqtt


def parse_payload(message: asyncio_mqtt.Message) -> dict[str, Any]:
  if not isinstance(message.payload, (str, bytes, bytearray)):
    raise ValueError('Expected message payload type to be str, bytes, or bytearray, '
                     f'got {type(message.payload)} instead.')

  try:
    payload = json.loads(message.payload)
  except:
    raise _value_error('Unable to decode JSON payload.', message.payload)

  if not isinstance(payload, dict):
    raise _value_error('Payload is not a dictionary.', payload)

  for key in payload.keys():
    if not isinstance(key, str):
      raise _value_error(f'Payload key {key} is not a string.', payload)

  return payload


def get_value(payload: dict[str, Any], key: str, expected_class: type):
  value = payload.get(key)

  if value is None or not isinstance(value, expected_class):
    raise _value_error(
        f'Expected value type {expected_class} for key "{key}" but got {type(value)}.', payload)

  return value


def get_value_or_none(payload: dict[str, Any], key: str, expected_class):
  value = payload.get(key)

  if value is not None and not isinstance(value, expected_class):
    raise _value_error(
        f'Expected value type {expected_class} for key "{key}" but got {type(value)}.', payload)

  return value


def _value_error(error_message: str, payload: Any) -> ValueError:
  e = ValueError(error_message)
  e.add_note(f'payload={str(payload)}')
  return e
