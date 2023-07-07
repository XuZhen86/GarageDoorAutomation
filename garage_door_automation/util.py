import json
from decimal import Decimal
from typing import Any

import asyncio_mqtt
from absl import flags


def parse_payload(message: asyncio_mqtt.Message) -> dict[str, Any]:
  assert isinstance(message.payload, (str, bytes, bytearray)), \
         f'Payload "{message.payload}" is not of type str, bytes, or bytearray. Got {type(message.payload)} instead.'

  try:
    payload = json.loads(message.payload)
  except json.decoder.JSONDecodeError as e:
    e.add_note(f'Unable to decode JSON payload "{message.payload}".')
    raise

  assert isinstance(payload, dict), \
         f'Payload "{payload}" is not a dictionary. Got {type(payload)} instead.'

  for key in payload.keys():
    assert isinstance(key, str), f'Key "{key}" is not a string. Got {type(key)} instead.'

  return payload


def _get_value(payload: dict[str, Any], key: str, expected_type: Any):
  value = payload.get(key)
  assert value is not None, f'Value for key "{key}" is None.'
  assert isinstance(value, expected_type), \
         f'Value "{value}" of key "{key}" is not of type {expected_type}.' \
         f'Got {type(value)} instead.'
  return value


def get_bool(payload: dict[str, Any], key: str) -> bool:
  return bool(_get_value(payload, key, bool))


def get_int(payload: dict[str, Any], key: str) -> int:
  return int(_get_value(payload, key, int))


def _get_value_or_none(payload: dict[str, Any], key: str, expected_type: Any):
  value = payload.get(key)
  if value is None:
    return None

  assert isinstance(value, expected_type), \
         f'Value "{value}" of key "{key}" is not of type {expected_type}. ' \
         f'Got {type(value)} instead.'
  return value


def get_bool_or_none(payload: dict[str, Any], key: str) -> bool | None:
  if (value := _get_value_or_none(payload, key, bool)) is None:
    return None
  return bool(value)


def get_int_or_none(payload: dict[str, Any], key: str) -> int | None:
  if (value := _get_value_or_none(payload, key, int)) is None:
    return None
  return int(value)


def get_str_or_none(payload: dict[str, Any], key: str) -> str | None:
  if (value := _get_value_or_none(payload, key, str)) is None:
    return None
  return str(value)


def get_decimal_or_none(payload: dict[str, Any], key: str) -> Decimal | None:
  if (value := _get_value_or_none(payload, key, (int, float))) is None:
    return None
  return Decimal(value)


def flag_length_validator(flag: dict[str, Any], expected_length: int) -> bool:
  for name, value in flag.items():
    if len(value) != expected_length:
      raise flags.ValidationError(f'Expected "{name}" to be of length {expected_length}. '
                                  f'Got {len(value)} instead.')
  return True


def int_or_none(value: Any | None) -> int | None:
  if value is None:
    return None
  return int(value)
