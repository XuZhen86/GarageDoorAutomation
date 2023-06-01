import time
from dataclasses import dataclass, asdict
from decimal import Decimal
from enum import StrEnum
from queue import Queue
from typing import Callable

import asyncio_mqtt
import requests
from absl import flags, logging
from influxdb_client import Point

from garage_door_automation.util import get_value, get_value_or_none, parse_payload

_MOTION_SENSOR_MQTT_TOPICS = flags.DEFINE_multi_string(
    name='motion_sensor_mqtt_topics',
    default=None,
    required=True,
    help='Specify the MQTT topics for the motion sensors.',
)

_MOTION_SENSOR_NICK_NAMES = flags.DEFINE_multi_string(
    name='motion_sensor_nick_names',
    default=None,
    required=True,
    help='Specify the nick names for the motion sensors.',
)

_MOTION_SENSOR_OCCUPANCY_WEBHOOKS = flags.DEFINE_multi_string(
    name='motion_sensor_occupancy_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when occupancy is detected. '
    'Use "-" if webhook for that sensor is disabled.',
)

_MOTION_SENSOR_VACANCY_WEBHOOKS = flags.DEFINE_multi_string(
    name='motion_sensor_vacancy_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when occupancy is no longer detected. '
    'Use "-" if webhook for that sensor is disabled.',
)


@dataclass(frozen=True)
class MotionSensor:
  mqtt_topic: str
  nick_name: str
  occupancy_webhook: str | None = None
  vacancy_webhook: str | None = None


_MOTION_SENSORS: dict[str, MotionSensor] = dict()


class MotionSensitivity(StrEnum):
  LOW = 'low'
  MEDIUM = 'medium'
  HIGH = 'high'
  VERY_HIGH = 'very_high'
  MAX = 'max'


@dataclass(frozen=True)
class MotionSensorDataPoint:
  motion_sensor: MotionSensor
  battery_percent: int
  is_occupied: bool
  link_quality: int

  is_illuminance_above_threshold: bool | None = None
  requested_brightness_level: int | None = None
  requested_brightness_percent: int | None = None

  has_led_indication: bool | None = None
  illuminance: int | None = None
  illuminance_lux: int | None = None
  motion_sensitivity: MotionSensitivity | None = None
  occupancy_timeout_s: int | None = None
  temperature_c_1000x: int | None = None

  def to_line_protocol(self, time_ns: int = time.time_ns()) -> str:
    # yapf: disable
    point = (Point('motion_sensor')
        .tag('nick_name', self.motion_sensor.nick_name)
        .tag('mqtt_topic', self.motion_sensor.mqtt_topic)
        .time(time_ns))  # type: ignore
    # yapf: enable

    for key, value in asdict(self).items():
      if value is not None:
        point.field(key, value)
    return point.to_line_protocol()


def _put_sensor_data_point(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  topic = message.topic.value
  motion_sensor = _MOTION_SENSORS.get(topic)
  if motion_sensor is None:
    logging.error(f'Unknown MQTT topic: {topic}')
    return

  try:
    payload = parse_payload(message)
    battery_percent: int = get_value(payload, 'battery', int)
    is_occupied: bool = get_value(payload, 'occupancy', bool)
    link_quality: int = get_value(payload, 'linkquality', int)
  except ValueError as e:
    logging.error(e)
    return

  try:
    is_illuminance_above_threshold: bool | None = get_value_or_none(payload,
                                                                    'illuminance_above_threshold',
                                                                    bool)
    requested_brightness_level: int | None = get_value_or_none(payload,
                                                               'requested_brightness_level', int)
    requested_brightness_percent: int | None = get_value_or_none(payload,
                                                                 'requested_brightness_percent',
                                                                 int)

    has_led_indication: bool | None = get_value_or_none(payload, 'led_indication', bool)
    illuminance: int | None = get_value_or_none(payload, 'illuminance', int)
    illuminance_lux: int | None = get_value_or_none(payload, 'illuminance_lux', int)
    motion_sensitivity_str: str | None = get_value_or_none(payload, 'motion_sensitivity', str)
    occupancy_timeout_s: int | None = get_value_or_none(payload, 'occupancy_timeout', int)
    temperature_c: int | None = get_value_or_none(payload, 'temperature', float)
  except ValueError as e:
    logging.error(e)
    return

  motion_sensitivity = MotionSensitivity(
      motion_sensitivity_str) if motion_sensitivity_str is not None else None
  temperature_c_1000x = int(Decimal(temperature_c) * 1000) if temperature_c is not None else None

  data_point = MotionSensorDataPoint(
      motion_sensor=_MOTION_SENSORS[message.topic.value],
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
  line_protocol_queue.put(data_point.to_line_protocol())


def _invoke_webhooks(message: asyncio_mqtt.Message) -> None:
  topic = message.topic.value
  motion_sensor = _MOTION_SENSORS.get(topic)
  if motion_sensor is None:
    logging.error(f'Unknown MQTT topic: {topic}')
    return

  try:
    payload = parse_payload(message)
    is_occupied: bool = get_value(payload, 'occupancy', bool)
  except ValueError as e:
    logging.error(e)
    return

  webhook_url = motion_sensor.occupancy_webhook if is_occupied else motion_sensor.vacancy_webhook
  if webhook_url is None:
    return

  response = requests.get(webhook_url, timeout=10)
  if response.status_code != 200:
    logging.error(f'Webhook invocation failed for motion sensor {motion_sensor.nick_name}, '
                  f'is_occupied={is_occupied}, '
                  f'status_code={response.status_code}.')


def _process_message(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  _put_sensor_data_point(message, line_protocol_queue)
  _invoke_webhooks(message)


def _process_flags() -> None:
  if len(_MOTION_SENSOR_MQTT_TOPICS.value) != len(_MOTION_SENSOR_NICK_NAMES.value) != len(
      _MOTION_SENSOR_OCCUPANCY_WEBHOOKS.value) != len(_MOTION_SENSOR_VACANCY_WEBHOOKS.value):
    raise ValueError('Length of flags motion_sensor_* are not the same.')

  for i, mqtt_topic in enumerate(_MOTION_SENSOR_MQTT_TOPICS.value):
    nick_name: str = _MOTION_SENSOR_NICK_NAMES.value[i]
    occupancy_webhook = (str(_MOTION_SENSOR_OCCUPANCY_WEBHOOKS.value[i])
                         if _MOTION_SENSOR_OCCUPANCY_WEBHOOKS.value[i] != '-' else None)
    vacancy_webhook = (str(_MOTION_SENSOR_VACANCY_WEBHOOKS.value[i])
                       if _MOTION_SENSOR_VACANCY_WEBHOOKS.value[i] != '-' else None)

    motion_sensor = MotionSensor(
        mqtt_topic=mqtt_topic,
        nick_name=nick_name,
        occupancy_webhook=occupancy_webhook,
        vacancy_webhook=vacancy_webhook,
    )
    _MOTION_SENSORS[mqtt_topic] = motion_sensor


def get_message_processors(
    line_protocol_queue: Queue[str]) -> dict[str, Callable[[asyncio_mqtt.Message], None]]:
  _process_flags()
  process_message = lambda message: _process_message(message, line_protocol_queue)
  return {topic: process_message for topic in _MOTION_SENSORS.keys()}
