import asyncio
import time
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from queue import Queue
from typing import Callable

import asyncio_mqtt
import requests
from absl import flags, logging
from influxdb_client import Point

from garage_door_automation.util import get_value, parse_payload

_CONTACT_SENSOR_MQTT_TOPICS = flags.DEFINE_multi_string(
    name='contact_sensor_mqtt_topics',
    default=None,
    required=True,
    help='Specify the MQTT topics for the contact sensors.',
)

_CONTACT_SENSOR_NICK_NAMES = flags.DEFINE_multi_string(
    name='contact_sensor_nick_names',
    default=None,
    required=True,
    help='Specify the nick names for the contact sensors.',
)

_CONTACT_SENSOR_CLOSED_WEBHOOKS = flags.DEFINE_multi_string(
    name='contact_sensor_closed_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when sensor is contacted. '
    'Use "-" if webhook for that sensor is disabled.',
)

_CONTACT_SENSOR_OPENED_WEBHOOKS = flags.DEFINE_multi_string(
    name='contact_sensor_opened_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when sensor is not contacted. '
    'Use "-" if webhook for that sensor is disabled.',
)


class Position(Enum):
  FULLY_CLOSED = auto()
  SLIGHTLY_OPENED = auto()
  FULLY_OPENED = auto()
  BACK_YARD_DOOR = auto()


_CONTACT_SENSOR_POSITIONS = flags.DEFINE_multi_enum_class(
    name='contact_sensor_positions',
    default=None,
    enum_class=Position,
    required=True,
    help='Specify the positions for the contact sensors',
)

_CONTACT_SENSOR_INITIAL_STATES = flags.DEFINE_multi_integer(
    name='contact_sensor_initial_states',
    default=[-1] * len(Position),
    upper_bound=1,
    lower_bound=-1,
    help='Manually override sensor is_contact status upon startup. '
    'Should only used for testing. '
    '-1 for undefined, 0 for not contacted, 1 for contacted.',
)
_CONTACT_SENSOR_STATE_VALIDITY_SECONDS = flags.DEFINE_integer(
    name='contact_sensor_state_validity_seconds',
    default=3060,
    help='Time in seconds where last reported sensor status should be valid for. '
    'This should be set to equal the sensor\'s periodic update time.',
)
_EXPECT_ENTER_MAX_SECONDS = flags.DEFINE_integer(
    name='expect_enter_max_seconds',
    lower_bound=0,
    upper_bound=30,
    default=15,
    help='Maximun amount of time in seconds to wait for the door to enter a position.',
)
_EXPECT_EXIT_MAX_SECONDS = flags.DEFINE_integer(
    name='expect_exit_max_seconds',
    lower_bound=0,
    upper_bound=30,
    default=2,
    help='Maximun amount of time in seconds to wait for the door to exit a position.',
)


@dataclass
class _ContactSensor:
  position: Position
  mqtt_topic: str
  nick_name: str
  _is_contact: bool = False
  closed_webhook: str | None = None
  opened_webhook: str | None = None

  # field() is needed to ensure a new Event is created for each ContactSensor instance.
  # Otherwise it would refer to the same Event instance.
  event: asyncio.Event = field(default_factory=asyncio.Event)
  last_updated_ns: int | None = None

  def set_is_contact(self, is_contact: bool) -> None:
    self._is_contact = is_contact
    self.last_updated_ns = time.time_ns()
    self.event.set()

  def get_is_contact(self) -> bool | None:
    return self._is_contact

  def is_valid(self) -> bool:
    if self.last_updated_ns is None:
      return False

    since_last_updated_s = (time.time_ns() - self.last_updated_ns) // (10**9)
    return since_last_updated_s < _CONTACT_SENSOR_STATE_VALIDITY_SECONDS.value

  def __str__(self) -> str:
    if not self.is_valid():
      state = '?'
    elif self._is_contact:
      state = '='
    else:
      state = '-'

    if self.last_updated_ns is None:
      return str(self.position.value) + state + '?'

    since_last_updated_s = (time.time_ns() - self.last_updated_ns) // (10**9)
    return str(self.position.value) + state + str(since_last_updated_s)


# Each sensor should have two mappings, one from MQTT topic and another from Position.
_CONTACT_SENSORS: dict[str | Position, _ContactSensor] = dict()


@dataclass(frozen=True)
class _ContactSensorDataPoint:
  _position: Position
  _mqtt_topic: str
  _nick_name: str

  battery_percent: int
  is_contact: bool
  last_updated_ns: int | None
  link_quality: int
  power_outage_count: int
  temperature_c: int
  voltage_mv: int

  def to_line_protocol(self, time_ns: int | None = None) -> str:
    point = Point('contact_sensor').time(
        time_ns if time_ns is not None else time.time_ns())  # type: ignore

    for key, value in asdict(self).items():
      if key.startswith('_'):
        point.tag(key[1:], value)
      else:
        point.field(key, value)

    return point.to_line_protocol()


def _update_sensor(message: asyncio_mqtt.Message) -> None:
  topic = message.topic.value
  contact_sensor = _CONTACT_SENSORS.get(topic)
  if contact_sensor is None:
    logging.error(f'Unknown MQTT topic: {topic}.')
    return

  try:
    payload = parse_payload(message)
    is_contact: bool = get_value(payload, 'contact', bool)
  except ValueError as e:
    logging.error(e)
    return

  contact_sensor.set_is_contact(is_contact)


def _put_sensor_data_point(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  topic = message.topic.value
  contact_sensor = _CONTACT_SENSORS.get(topic)
  if contact_sensor is None:
    logging.error(f'Unknown MQTT topic: {topic}.')
    return

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

  data_point = _ContactSensorDataPoint(
      _position=contact_sensor.position,
      _mqtt_topic=contact_sensor.mqtt_topic,
      _nick_name=contact_sensor.nick_name,
      battery_percent=battery_percent,
      is_contact=is_contact,
      last_updated_ns=contact_sensor.last_updated_ns,
      link_quality=link_quality,
      power_outage_count=power_outage_count,
      temperature_c=temperature_c,
      voltage_mv=voltage_mv,
  )
  line_protocol_queue.put(data_point.to_line_protocol())


def _invoke_webhooks(message: asyncio_mqtt.Message) -> None:
  topic = message.topic.value
  contact_sensor = _CONTACT_SENSORS.get(topic)
  if contact_sensor is None:
    logging.error(f'Unknown MQTT topic: {topic}')
    return

  try:
    payload = parse_payload(message)
    is_contact: bool = get_value(payload, 'contact', bool)
  except ValueError as e:
    logging.error(e)
    return

  webhook_url = contact_sensor.closed_webhook if is_contact else contact_sensor.opened_webhook
  if webhook_url is None:
    return

  response = requests.get(webhook_url, timeout=10)
  if response.status_code != 200:
    logging.error(f'Webhook invocation failed for motion sensor {contact_sensor.nick_name}, '
                  f'is_contact={is_contact}, '
                  f'status_code={response.status_code}.')


def _process_message(message: asyncio_mqtt.Message, line_protocol_queue: Queue[str]) -> None:
  _update_sensor(message)
  _put_sensor_data_point(message, line_protocol_queue)
  _invoke_webhooks(message)


def _process_flags() -> None:
  if not (len(Position) == len(_CONTACT_SENSOR_MQTT_TOPICS.value) == len(
      _CONTACT_SENSOR_NICK_NAMES.value) == len(_CONTACT_SENSOR_POSITIONS.value) == len(
          _CONTACT_SENSOR_INITIAL_STATES.value) == len(_CONTACT_SENSOR_CLOSED_WEBHOOKS.value) ==
          len(_CONTACT_SENSOR_OPENED_WEBHOOKS.value)):
    e = ValueError('Length of flags contact_sensor_* are not the same. '
                   f'The length should equal to {len(Position)}.')
    e.add_note(f'len(_CONTACT_SENSOR_MQTT_TOPICS.value)={len(_CONTACT_SENSOR_MQTT_TOPICS.value)}')
    e.add_note(f'len(_CONTACT_SENSOR_NICK_NAMES.value)={len(_CONTACT_SENSOR_NICK_NAMES.value)}')
    e.add_note(f'len(_CONTACT_SENSOR_POSITIONS.value)={len(_CONTACT_SENSOR_POSITIONS.value)}')
    e.add_note(
        f'len(_CONTACT_SENSOR_INITIAL_STATES.value)={len(_CONTACT_SENSOR_INITIAL_STATES.value)}')
    e.add_note(
        f'len(_CONTACT_SENSOR_CLOSED_WEBHOOKS.value)={len(_CONTACT_SENSOR_CLOSED_WEBHOOKS.value)}')
    e.add_note(
        f'len(_CONTACT_SENSOR_OPENED_WEBHOOKS.value)={len(_CONTACT_SENSOR_OPENED_WEBHOOKS.value)}')
    raise e

  for i, mqtt_topic in enumerate(_CONTACT_SENSOR_MQTT_TOPICS.value):
    nick_name: str = _CONTACT_SENSOR_NICK_NAMES.value[i]
    position: Position = _CONTACT_SENSOR_POSITIONS.value[i]
    closed_webhook = (str(_CONTACT_SENSOR_CLOSED_WEBHOOKS.value[i])
                      if _CONTACT_SENSOR_CLOSED_WEBHOOKS.value[i] != '-' else None)
    opened_webhook = (str(_CONTACT_SENSOR_OPENED_WEBHOOKS.value[i])
                      if _CONTACT_SENSOR_OPENED_WEBHOOKS.value[i] != '-' else None)

    contact_sensor = _ContactSensor(
        mqtt_topic=mqtt_topic,
        position=position,
        nick_name=nick_name,
        closed_webhook=closed_webhook,
        opened_webhook=opened_webhook,
    )

    initial_state: int = _CONTACT_SENSOR_INITIAL_STATES.value[i]
    if initial_state != -1:
      contact_sensor.set_is_contact(bool(initial_state))

    _CONTACT_SENSORS[mqtt_topic] = contact_sensor
    _CONTACT_SENSORS[position] = contact_sensor


def get_message_processors(
    line_protocol_queue: Queue[str]) -> dict[str, Callable[[asyncio_mqtt.Message], None]]:
  _process_flags()
  process_message = lambda message: _process_message(message, line_protocol_queue)
  return {topic: process_message for topic in _CONTACT_SENSOR_MQTT_TOPICS.value}


def at(position: Position) -> bool:
  return _CONTACT_SENSORS[position].get_is_contact() == True


def expect_at(position: Position) -> None:
  assert at(position), f'Expected door to be at {position.name}.'


def expect_not_at(position: Position) -> None:
  assert not at(position), f'Expected door to not be at {position.name}.'


async def _enter(position: Position, timeout_s: float) -> bool:
  if at(position):
    logging.error(f'Door already at {position.name}.')
    return False

  sensor = _CONTACT_SENSORS[position]
  sensor.event.clear()
  logging.info(f'Waiting for door to enter {position.name} within {timeout_s}s.')

  try:
    await asyncio.wait_for(sensor.event.wait(), timeout_s)
  except TimeoutError:
    logging.error(f'Expected sensor at {position.name} to trigger within {timeout_s}s, '
                  'but it has not.')
    return False

  if not at(position):
    logging.error(f'Sensor at {position.name} was triggered, '
                  'but the value indicates the door is not at this position.')
    return False

  logging.info(f'Door has entered {position.name}.')
  return True


async def _exit(position: Position, timeout_s: float) -> bool:
  if not at(position):
    logging.error(f'Door not already at {position.name}.')
    return False

  sensor = _CONTACT_SENSORS[position]
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


async def expect_enter(position: Position, timeout_s: float | None = None) -> None:
  if timeout_s is None:
    timeout_s = float(_EXPECT_ENTER_MAX_SECONDS.value)
  assert await _enter(position, timeout_s), f'Door did not enter {position.name}.'


async def expect_exit(position: Position, timeout_s: float | None = None) -> None:
  if timeout_s is None:
    timeout_s = float(_EXPECT_EXIT_MAX_SECONDS.value)
  assert await _exit(position, timeout_s), f'Door did not exit {position.name}.'


def where() -> Position | None:
  for position in Position:
    if at(position):
      return position
  return None
