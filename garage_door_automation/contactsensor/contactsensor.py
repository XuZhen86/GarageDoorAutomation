import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from absl import flags, logging

from garage_door_automation.contactsensor.flag import (CLOSED_WEBHOOKS, EXPECT_ENTER_MAX_SECONDS,
                                                       EXPECT_EXIT_MAX_SECONDS, INITIAL_STATES,
                                                       MQTT_TOPICS, NICK_NAMES, OPENED_WEBHOOKS,
                                                       POSITIONS, STATE_VALIDITY_SECONDS)
from garage_door_automation.contactsensor.position import Position
from garage_door_automation.util import flag_length_validator


def _process_flags(flag: dict[str, Any]) -> bool:
  flag_length_validator(flag, len(Position))

  if set(POSITIONS.value) != set(Position):
    raise flags.ValidationError('Each position must be specified exactly once.')

  for i in range(len(Position)):
    sensor = ContactSensor(
        position=Position(POSITIONS.value[i]),
        mqtt_topic=str(MQTT_TOPICS.value[i]),
        nick_name=str(NICK_NAMES.value[i]),
        closed_webhook=str(CLOSED_WEBHOOKS.value[i]) if CLOSED_WEBHOOKS.value[i] != '-' else None,
        opened_webhook=str(OPENED_WEBHOOKS.value[i]) if OPENED_WEBHOOKS.value[i] != '-' else None,
    )

    initial_state = int(INITIAL_STATES.value[i])
    if initial_state != -1:
      sensor.set_is_contact(bool(initial_state))

    _SENSORS[sensor.mqtt_topic] = sensor
    _SENSORS[sensor.position] = sensor

  return True


flags.register_multi_flags_validator(
    [CLOSED_WEBHOOKS, INITIAL_STATES, MQTT_TOPICS, NICK_NAMES, OPENED_WEBHOOKS, POSITIONS],
    _process_flags)


@dataclass
class ContactSensor:
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
    return since_last_updated_s < int(STATE_VALIDITY_SECONDS.value)

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
_SENSORS: dict[str | Position, ContactSensor] = dict()


def get_sensor(key: str | Position) -> ContactSensor:
  if key not in _SENSORS:
    raise ValueError(f'Unexpected contact sensor {key=}.')
  return _SENSORS[key]


def at(position: Position) -> bool:
  return get_sensor(position).get_is_contact() == True


def expect_at(position: Position) -> None:
  assert at(position), f'Expected door to be at {position.name}.'


def expect_not_at(position: Position) -> None:
  assert not at(position), f'Expected door to not be at {position.name}.'


async def _enter(position: Position, timeout_s: float) -> bool:
  if at(position):
    logging.error(f'Door already at {position.name}.')
    return False

  sensor = get_sensor(position)
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

  sensor = get_sensor(position)
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
    timeout_s = float(EXPECT_ENTER_MAX_SECONDS.value)
  assert await _enter(position, timeout_s), f'Door did not enter {position.name}.'


async def expect_exit(position: Position, timeout_s: float | None = None) -> None:
  if timeout_s is None:
    timeout_s = float(EXPECT_EXIT_MAX_SECONDS.value)
  assert await _exit(position, timeout_s), f'Door did not exit {position.name}.'


def where(
    positions_to_check: list[Position] = [
        Position.FULLY_CLOSED,
        Position.SLIGHTLY_OPENED,
        Position.FULLY_OPENED,
    ]
) -> Position | None:
  for position in positions_to_check:
    if at(position):
      return position
  return None
