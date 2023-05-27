import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from queue import Queue
from typing import Callable

import asyncio_mqtt
import requests
from absl import flags, logging
from influxdb_client import Point

from garage_door_automation.util import get_value, parse_payload

_INDOOR_MOTION_SENSOR_TOPIC = flags.DEFINE_string(
    name='indoor_motion_sensor_topic',
    default=None,
    required=True,
    help='Specify the MQTT topics for the indoor motion sensor.',
)

_OUTDOOR_MOTION_SENSOR_TOPIC = flags.DEFINE_string(
    name='outdoor_motion_sensor_topic',
    default=None,
    required=True,
    help='Specify the MQTT topics for the outdoor motion sensor.',
)

_OUTDOOR_MOTION_SENSOR_OCCUPANCY_WEBHOOK = flags.DEFINE_string(
    name='outdoor_motion_sensor_occupancy_webhook',
    default=None,
    required=False,
    help='Specify the webhook to invoke when occupancy is detected.',
)

_OUTDOOR_MOTION_SENSOR_VACANCY_WEBHOOK = flags.DEFINE_string(
    name='outdoor_motion_sensor_vacancy_webhook',
    default=None,
    required=False,
    help='Specify the webhook to invoke when occupancy is no longer detected.',
)


@dataclass
class IndoorMotionSensorTimestamp:
  battery_percent: int
  is_illuminance_above_threshold: bool
  is_occupied: bool
  link_quality: int
  requested_brightness_level: int
  requested_brightness_percent: int

  time_ns: int = field(default_factory=time.time_ns)

  def to_line_protocol(self) -> str:
    # yapf: disable
    return (Point
        .measurement('motion_sensor')
        .tag('position', 'indoor')
        .field('battery_percent', self.battery_percent)
        .field('is_illuminance_above_threshold',int(self.is_illuminance_above_threshold))
        .field('is_occupied', int(self.is_occupied))
        .field('link_quality', self.link_quality)
        .field('requested_brightness_level', self.requested_brightness_level)
        .field('requested_brightness_percent', self.requested_brightness_percent)
        .time(self.time_ns)  # type: ignore
        .to_line_protocol())
    # yapf: enable


class OutdoorMotionSensorMotionSensitivity(StrEnum):
  LOW = 'low'
  MEDIUM = 'medium'
  HIGH = 'high'
  VERY_HIGH = 'very_high'
  MAX = 'max'


@dataclass
class OutdoorMotionSensorTimestamp:
  battery_percent: int
  has_led_indication: bool
  illuminance: int
  illuminance_lux: int
  is_occupied: bool
  link_quality: int
  motion_sensitivity: OutdoorMotionSensorMotionSensitivity
  occupancy_timeout_s: int
  temperature_c_1000x: int

  time_ns: int = field(default_factory=time.time_ns)

  def to_line_protocol(self) -> str:
    # yapf: disable
    return (Point
        .measurement('motion_sensor')
        .tag('position', 'outdoor')
        .field('battery_percent', self.battery_percent)
        .field('has_led_indication', int(self.has_led_indication))
        .field('illuminance', self.illuminance)
        .field('illuminance_lux', self.illuminance_lux)
        .field('is_occupied', int(self.is_occupied))
        .field('link_quality', self.link_quality)
        .field('motion_sensitivity', str(self.motion_sensitivity))
        .field('occupancy_timeout_s', self.occupancy_timeout_s)
        .field('temperature_c_1000x', self.temperature_c_1000x)
        .time(self.time_ns)  # type: ignore
        .to_line_protocol())
    # yapf: enable


def _put_sensor_datapoint(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  try:
    payload = parse_payload(message)
    if message.topic.value == _INDOOR_MOTION_SENSOR_TOPIC.value:
      sensor_timestamp = IndoorMotionSensorTimestamp(
          battery_percent=get_value(payload, 'battery', int),
          is_illuminance_above_threshold=get_value(payload, 'illuminance_above_threshold', bool),
          is_occupied=get_value(payload, 'occupancy', bool),
          link_quality=get_value(payload, 'linkquality', int),
          requested_brightness_level=get_value(payload, 'requested_brightness_level', int),
          requested_brightness_percent=get_value(payload, 'requested_brightness_percent', int),
      )
    else:
      sensor_timestamp = OutdoorMotionSensorTimestamp(
          battery_percent=get_value(payload, 'battery', int),
          has_led_indication=get_value(payload, 'led_indication', bool),
          illuminance=get_value(payload, 'illuminance', int),
          illuminance_lux=get_value(payload, 'illuminance_lux', int),
          is_occupied=get_value(payload, 'occupancy', bool),
          link_quality=get_value(payload, 'linkquality', int),
          motion_sensitivity=OutdoorMotionSensorMotionSensitivity(
              get_value(payload, 'motion_sensitivity', str)),
          occupancy_timeout_s=get_value(payload, 'occupancy_timeout', int),
          temperature_c_1000x=int(Decimal(get_value(payload, 'temperature', float)) * 1000),
      )
  except ValueError as e:
    logging.error(e)
    return

  line_protocol_queue.put(sensor_timestamp.to_line_protocol())


def _invoke_webhooks(message: asyncio_mqtt.Message) -> None:
  if message.topic.value != _OUTDOOR_MOTION_SENSOR_TOPIC.value:
    return

  try:
    payload = parse_payload(message)
    is_occupied = get_value(payload, 'occupancy', bool)
  except ValueError as e:
    logging.error(e)
    return

  webhook_url: str | None = None
  if is_occupied and _OUTDOOR_MOTION_SENSOR_OCCUPANCY_WEBHOOK.present:
    webhook_url = _OUTDOOR_MOTION_SENSOR_OCCUPANCY_WEBHOOK.value
  if not is_occupied and _OUTDOOR_MOTION_SENSOR_VACANCY_WEBHOOK.present:
    webhook_url = _OUTDOOR_MOTION_SENSOR_VACANCY_WEBHOOK.value

  if webhook_url is None:
    return

  response = requests.get(webhook_url, timeout=10)
  if response.status_code != 200:
    logging.error(f'Webhook invocation failed, status_code={response.status_code}.')


def _process_message(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  _put_sensor_datapoint(message, line_protocol_queue)
  _invoke_webhooks(message)


def get_message_processors(
    line_protocol_queue: Queue[str]) -> dict[str, Callable[[asyncio_mqtt.Message], None]]:
  process_message = lambda message: _process_message(message, line_protocol_queue)
  return {
      _INDOOR_MOTION_SENSOR_TOPIC.value: process_message,
      _OUTDOOR_MOTION_SENSOR_TOPIC.value: process_message,
  }
