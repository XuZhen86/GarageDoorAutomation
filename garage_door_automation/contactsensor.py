import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from queue import Queue
from typing import Callable

import asyncio_mqtt
from absl import flags, logging
from influxdb_client import Point

from garage_door_automation.mqtt import get_value, parse_payload


class Position(IntEnum):
  FULLY_CLOSED = 0
  SLIGHTLY_OPEN = 1
  FULLY_OPEN = 2


_CONTACT_SENSOR_TOPICS = flags.DEFINE_multi_string(
    name='contact_sensor_topics',
    default=None,
    required=True,
    help='Specify the MQTT topics for the contact sensors. ' +
    f'Must be specified in order for: {[position.name for position in Position]}',
)
_CONTACT_SENSOR_STATE_VALIDITY_SECONDS = flags.DEFINE_integer(
    name='contact_sensor_state_validity_seconds',
    default=None,
    required=True,
    help='Time in seconds where last reported sensor status should be valid for. '
    'This should be set to equal the sensor\'s periodic update time.',
)

_CONTACT_SENSOR_INITIAL_STATES = flags.DEFINE_multi_integer(
    name='contact_sensor_initial_states',
    default=None,
    required=False,
    help='Manually override sensor is_contact status upon startup. '
    'Should only used for testing.',
)

_EXPECT_ENTER_MAX_SECONDS = flags.DEFINE_integer(
    name='expect_enter_max_seconds',
    lower_bound=0,
    upper_bound=30,
    required=True,
    default=None,
    help='Maximun amount of time in seconds to wait for the door to enter a position.',
)
_EXPECT_EXIT_MAX_SECONDS = flags.DEFINE_integer(
    name='expect_exit_max_seconds',
    lower_bound=0,
    upper_bound=30,
    required=True,
    default=None,
    help='Maximun amount of time in seconds to wait for the door to exit a position.',
)


@dataclass
class ContactSensor:
  position: Position
  topic: str | None = None
  # field() is needed to ensure a new Event is created for each ContactSensor instance.
  # Otherwise it would refer to the same Event instance.
  event: asyncio.Event = field(default_factory=asyncio.Event)

  _is_contact: bool = False
  _last_updated_ns: int | None = None

  @property
  def is_contact(self) -> bool | None:
    if not self.is_valid():
      since_last_updated_s = ((time.time_ns() - self._last_updated_ns) //
                              10**9) if self._last_updated_ns is not None else '?'
      logging.warning(f'Sensor at {self.position.name} has invalid state. '
                      f'Last updated at {since_last_updated_s}s before.')
      return None
    return self._is_contact

  def set_is_contact(self, value: bool) -> int | None:
    self._is_contact = value
    last_updated_ns = self._last_updated_ns
    self._last_updated_ns = time.time_ns()
    return self._last_updated_ns - last_updated_ns if last_updated_ns is not None else None

  def is_valid(self) -> bool:
    return (self._last_updated_ns is not None and time.time_ns() - self._last_updated_ns
            < _CONTACT_SENSOR_STATE_VALIDITY_SECONDS.value * (10**9))

  def __str__(self) -> str:
    if not self.is_valid():
      state = '?'
    elif self._is_contact:
      state = '='
    else:
      state = '-'
    since_last_updated_s = ((time.time_ns() - self._last_updated_ns) //
                            10**9) if self._last_updated_ns is not None else '?'
    return str(self.position.value) + state + str(since_last_updated_s)


_SENSORS = {position: ContactSensor(position) for position in Position}


@dataclass
class ContactSensorTimestamp:
  battery_percent: int
  is_contact: bool
  link_quality: int
  position: Position
  power_outage_count: int
  since_last_update_ns: int | None
  temperature_c: int
  voltage_mv: int

  time_ns: int = field(default_factory=time.time_ns)

  def to_line_protocol(self) -> str:
    # yapf: disable
    return (Point
        .measurement('contact_sensor')
        .tag('position', self.position.name.lower())
        .field('battery_percent', self.battery_percent)
        .field('is_contact', int(self.is_contact))
        .field('link_quality', self.link_quality)
        .field('power_outage_count', self.power_outage_count)
        .field('since_last_update_ns', self.since_last_update_ns if self.since_last_update_ns is not None else -1)
        .field('temperature_c', self.temperature_c)
        .field('voltage_mv', self.voltage_mv)
        .time(self.time_ns)  # type: ignore
        .to_line_protocol()
    )
    # yapf: enable


def _process_message(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  try:
    payload = parse_payload(message)
    battery_percent: int = get_value(payload, 'battery', int)
    is_contact: bool = get_value(payload, 'contact', bool)
    link_quality: int = get_value(payload, 'linkquality', int)
    power_outage_count: int = get_value(payload, 'power_outage_count', int)
    temperature_c: int = get_value(payload, 'device_temperature', int)
    voltage_mv: int = get_value(payload, 'voltage', int)
  except ValueError as e:
    logging.error(e)
    return

  topic = message.topic.value
  for sensor in _SENSORS.values():
    if sensor.topic != topic:
      continue

    since_last_update_ns = sensor.set_is_contact(is_contact)
    sensor.event.set()
    sensor_status = ', '.join([str(sensor) for sensor in _SENSORS.values()])
    logging.info(f'Sensor status: {sensor_status}')

    line_protocol_queue.put(
        ContactSensorTimestamp(
            battery_percent=battery_percent,
            is_contact=is_contact,
            link_quality=link_quality,
            position=sensor.position,
            power_outage_count=power_outage_count,
            since_last_update_ns=since_last_update_ns,
            temperature_c=temperature_c,
            voltage_mv=voltage_mv,
        ).to_line_protocol())
    return

  logging.error(f'No sensor matched topic "{topic}".')


def get_message_processors(
    line_protocol_queue: Queue[str]) -> dict[str, Callable[[asyncio_mqtt.Message], None]]:
  if len(_CONTACT_SENSOR_TOPICS.value) != len(Position):
    raise ValueError(f'Expected {len(Position)} MQTT topics, '
                     f'got {len(_CONTACT_SENSOR_TOPICS.value)} instead.')

  if _CONTACT_SENSOR_INITIAL_STATES.value is not None:
    if len(_CONTACT_SENSOR_INITIAL_STATES.value) != len(Position):
      raise ValueError()

    for i, state in enumerate(_CONTACT_SENSOR_INITIAL_STATES.value):
      _SENSORS[Position(i)].set_is_contact(state != 0)
    logging.debug([sensor.is_contact for sensor in _SENSORS.values()])

  topic: str
  for i, topic in enumerate(_CONTACT_SENSOR_TOPICS.value):
    _SENSORS[Position(i)].topic = topic

  process_message = lambda message: _process_message(message, line_protocol_queue)
  return {topic: process_message for topic in _CONTACT_SENSOR_TOPICS.value}


def where() -> Position | None:
  for position in Position:
    if at(position):
      return position
  return None


def at(position: Position, mock: bool = False) -> bool:
  return mock or _SENSORS[position].is_contact == True


def expect_at(position: Position, mock: bool = False) -> None:
  assert at(position, mock), f'Expected door to be at {position.name}.'


def expect_not_at(position: Position, mock: bool = False) -> None:
  assert not at(position, mock), f'Expected door to not be at {position.name}.'


async def _enter(position: Position, timeout_s: float, mock: bool = False) -> bool:
  if mock:
    logging.info(f'Mock entering {position.name} after {timeout_s/2}s.')
    await asyncio.sleep(timeout_s / 2)
    return True

  if at(position):
    logging.error(f'Door already at {position.name}.')
    return False

  sensor = _SENSORS[position]
  sensor.event.clear()
  logging.info(f'Waiting for door to enter {position.name} within {timeout_s}s.')

  try:
    await asyncio.wait_for(sensor.event.wait(), timeout_s)
  except TimeoutError:
    logging.error(f'Expected sensor at {position.name} to trigger within {timeout_s}s.'
                  'but it has not.')
    return False

  if not at(position):
    logging.error(f'Sensor at {position.name} was triggered, '
                  'but the value indicates the door is not at this position.')
    return False

  logging.info(f'Door has entered {position.name}.')
  return True


async def expect_enter(
    position: Position,
    timeout_s: float | None = None,
    mock: bool = False,
) -> None:
  if timeout_s is None:
    timeout_s = float(_EXPECT_ENTER_MAX_SECONDS.value)
  assert await _enter(position, timeout_s, mock), f'Door did not enter {position.name}.'


async def _exit(position: Position, timeout_s: float, mock: bool = False) -> bool:
  if mock:
    logging.info(f'Mock exiting {position.name} after {timeout_s/2}s.')
    await asyncio.sleep(timeout_s / 2)
    return True

  if not at(position):
    logging.error(f'Door not already at {position.name}.')
    return False

  sensor = _SENSORS[position]
  sensor.event.clear()
  logging.info(f'Waiting for door to exit {position.name} within {timeout_s}s.')

  try:
    await asyncio.wait_for(sensor.event.wait(), timeout_s)
  except TimeoutError:
    logging.error(f'Expected sensor at {position.name} to trigger within {timeout_s}s, '
                  'but it has not.')
    return False

  if at(position):
    logging.error(f'Sensor at {position.name} was triggered, '
                  'but the value indicates the door is still at this position.')
    return False

  logging.info(f'Door has exited {position.name}.')
  return True


async def expect_exit(
    position: Position,
    timeout_s: float | None = None,
    mock: bool = False,
) -> None:
  if timeout_s is None:
    timeout_s = float(_EXPECT_EXIT_MAX_SECONDS.value)
  assert await _exit(position, timeout_s, mock), f'Door did not exit {position.name}.'
