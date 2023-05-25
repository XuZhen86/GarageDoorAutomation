import time
from dataclasses import dataclass, field
from queue import Queue
from typing import Callable

import asyncio_mqtt
from absl import flags, logging
from influxdb_client import Point

from garage_door_automation.mqtt import get_value, parse_payload

_MOTION_SENSOR_TOPIC = flags.DEFINE_string(
    name='motion_sensor_topic',
    default=None,
    required=True,
    help='Specify the MQTT topics for the motion sensor.',
)


@dataclass
class MotionSensorTimestamp:
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
        .field('battery_percent', self.battery_percent)
        .field('is_illuminance_above_threshold',int(self.is_illuminance_above_threshold))
        .field('is_occupied', int(self.is_occupied))
        .field('link_quality', self.link_quality)
        .field('requested_brightness_level', self.requested_brightness_level)
        .field('requested_brightness_percent', self.requested_brightness_percent)
        .time(self.time_ns)  # type: ignore
        .to_line_protocol())
    # yapf: enable


def _process_message(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  try:
    payload = parse_payload(message)
    batter_percent: int = get_value(payload, 'battery', int)
    is_illuminance_above_threshold: bool = get_value(payload, 'illuminance_above_threshold', bool)
    is_occupied: bool = get_value(payload, 'occupancy', bool)
    link_quality: int = get_value(payload, 'linkquality', int)
    requested_brightness_level: int = get_value(payload, 'requested_brightness_level', int)
    requested_brightness_percent: int = get_value(payload, 'requested_brightness_percent', int)
  except ValueError as e:
    logging.error(e)
    return

  line_protocol_queue.put(
      MotionSensorTimestamp(
          battery_percent=batter_percent,
          is_illuminance_above_threshold=is_illuminance_above_threshold,
          is_occupied=is_occupied,
          link_quality=link_quality,
          requested_brightness_level=requested_brightness_level,
          requested_brightness_percent=requested_brightness_percent,
      ).to_line_protocol())


def get_message_processors(
    line_protocol_queue: Queue[str]) -> dict[str, Callable[[asyncio_mqtt.Message], None]]:
  process_message = lambda message: _process_message(message, line_protocol_queue)
  return {_MOTION_SENSOR_TOPIC.value: process_message}
