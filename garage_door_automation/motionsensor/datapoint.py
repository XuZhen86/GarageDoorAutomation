import time
from dataclasses import asdict, dataclass
from enum import StrEnum, unique
from json.decoder import JSONDecodeError

import asyncio_mqtt
from absl import logging
from influxdb_client import Point

from garage_door_automation.motionsensor.motionsensor import get_sensor
from garage_door_automation.util import (get_bool, get_bool_or_none, get_decimal_or_none, get_int,
                                         get_int_or_none, get_str_or_none, parse_payload)


@unique
class _MotionSensitivity(StrEnum):
  LOW = 'low'
  MEDIUM = 'medium'
  HIGH = 'high'
  VERY_HIGH = 'very_high'
  MAX = 'max'


@dataclass(frozen=True)
class _DataPoint:
  _nick_name: str
  _mqtt_topic: str

  battery_percent: int
  is_occupied: bool
  link_quality: int

  is_illuminance_above_threshold: bool | None = None
  requested_brightness_level: int | None = None
  requested_brightness_percent: int | None = None

  has_led_indication: bool | None = None
  illuminance: int | None = None
  illuminance_lux: int | None = None
  motion_sensitivity: _MotionSensitivity | None = None
  occupancy_timeout_s: int | None = None
  temperature_c_1000x: int | None = None

  def to_line_protocol(self, time_ns: int | None = None) -> str:
    point = Point('motion_sensor')
    point.time(time_ns if time_ns is not None else time.time_ns())  # type: ignore

    for key, value in asdict(self).items():
      if key.startswith('_'):
        point.tag(key[1:], value)
      else:
        point.field(key, value)

    return point.to_line_protocol()


def generate_data_point(message: asyncio_mqtt.Message) -> list[str]:
  topic = message.topic.value
  try:
    sensor = get_sensor(topic)
  except ValueError as e:
    e.add_note(f'Unknown MQTT {topic=}.')
    logging.exception(e)
    return []

  try:
    payload = parse_payload(message)
    battery_percent = get_int(payload, 'battery')
    is_occupied = get_bool(payload, 'occupancy')
    link_quality = get_int(payload, 'linkquality')
  except (JSONDecodeError, AssertionError) as e:
    logging.error(e)
    return []

  try:
    is_illuminance_above_threshold = get_bool_or_none(payload, 'illuminance_above_threshold')
    requested_brightness_level = get_int_or_none(payload, 'requested_brightness_level')
    requested_brightness_percent = get_int_or_none(payload, 'requested_brightness_percent')
    has_led_indication = get_bool_or_none(payload, 'led_indication')
    illuminance = get_int_or_none(payload, 'illuminance')
    illuminance_lux = get_int_or_none(payload, 'illuminance_lux')
    motion_sensitivity_str = get_str_or_none(payload, 'motion_sensitivity')
    occupancy_timeout_s = get_int_or_none(payload, 'occupancy_timeout')
    temperature_c = get_decimal_or_none(payload, 'temperature')
  except ValueError as e:
    logging.error(e)
    return []

  motion_sensitivity = _MotionSensitivity(
      motion_sensitivity_str) if motion_sensitivity_str is not None else None
  temperature_c_1000x = int(temperature_c * 1000) if temperature_c is not None else None

  data_point = _DataPoint(
      _mqtt_topic=sensor.mqtt_topic,
      _nick_name=sensor.nick_name,
      battery_percent=battery_percent,
      is_occupied=is_occupied,
      link_quality=link_quality,
      is_illuminance_above_threshold=is_illuminance_above_threshold,
      requested_brightness_level=requested_brightness_level,
      requested_brightness_percent=requested_brightness_percent,
      has_led_indication=has_led_indication,
      illuminance=illuminance,
      illuminance_lux=illuminance_lux,
      motion_sensitivity=motion_sensitivity,
      occupancy_timeout_s=occupancy_timeout_s,
      temperature_c_1000x=temperature_c_1000x,
  )
  return [data_point.to_line_protocol()]
