import json
import time
from dataclasses import dataclass, field
from queue import Queue
from typing import Any, Callable

import asyncio_mqtt
from absl import flags, logging
from influxdb_client import Point

_MOTION_SENSOR_TOPIC = flags.DEFINE_string(
    name='motion_sensor_topic',
    default=None,
    required=True,
    help='Specify the MQTT topics for the motion sensor.',
)


@dataclass
class MotionSensorTimestamp:
  is_occupied: bool
  is_illuminance_above_threshold: bool
  time_ns: int = field(default_factory=time.time_ns)

  def to_line_protocol(self) -> str:
    # yapf: disable
    return (Point
        .measurement('motion_sensor')
        .field('is_occupied', int(self.is_occupied))
        .field('is_illuminance_above_threshold',int(self.is_illuminance_above_threshold))
        .time(self.time_ns)  # type: ignore
        .to_line_protocol())
    # yapf: enable


def _process_message(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  if not isinstance(message.payload, (str, bytes, bytearray)):
    logging.error('Expected message payload type to be str, bytes, or bytearray.')
    return

  try:
    payload: dict[str, Any] = json.loads(message.payload)
  except:
    logging.error('Unable to decode JSON payload.')
    return

  is_occupied = payload.get('occupancy')
  if not isinstance(is_occupied, bool):
    logging.error('Invalid value type for key "occupancy".')
    return

  is_illuminance_above_threshold = payload.get('illuminance_above_threshold')
  if not isinstance(is_illuminance_above_threshold, bool):
    logging.error('Invalid value type for key "illuminance_above_threshold".')
    return

  line_protocol_queue.put(
      MotionSensorTimestamp(
          is_occupied=is_occupied,
          is_illuminance_above_threshold=is_illuminance_above_threshold,
      ).to_line_protocol())
  return


def get_message_processors(
    line_protocol_queue: Queue[str]) -> dict[str, Callable[[asyncio_mqtt.Message], None]]:
  process_message = lambda message: _process_message(message, line_protocol_queue)
  return {_MOTION_SENSOR_TOPIC.value: process_message}
