from dataclasses import dataclass
from typing import Any

from absl import flags

from garage_door_automation.motionsensor.flag import (MQTT_TOPICS, NICK_NAMES, OCCUPANCY_WEBHOOKS,
                                                      VACANCY_WEBHOOKS)
from garage_door_automation.util import flag_length_validator


def _process_flags(flag: dict[str, Any]) -> bool:
  flag_length_validator(flag, len(MQTT_TOPICS.value))

  for i in range(len(MQTT_TOPICS.value)):
    sensor = MotionSensor(
        mqtt_topic=str(MQTT_TOPICS.value[i]),
        nick_name=str(NICK_NAMES.value[i]),
        occupancy_webhook=str(OCCUPANCY_WEBHOOKS.value[i])
        if OCCUPANCY_WEBHOOKS.value[i] != '-' else None,
        vacancy_webhook=str(VACANCY_WEBHOOKS.value[i])
        if VACANCY_WEBHOOKS.value[i] != '-' else None,
    )
    _SENSORS[sensor.mqtt_topic] = sensor

  return True


flags.register_multi_flags_validator(
    [MQTT_TOPICS, NICK_NAMES, OCCUPANCY_WEBHOOKS, VACANCY_WEBHOOKS],
    _process_flags,
)


@dataclass(frozen=True)
class MotionSensor:
  mqtt_topic: str
  nick_name: str
  occupancy_webhook: str | None = None
  vacancy_webhook: str | None = None


_SENSORS: dict[str, MotionSensor] = dict()


def get_sensor(key: str) -> MotionSensor:
  if key not in _SENSORS:
    raise ValueError(f'Unexpected motion sensor "{key=}".')
  return _SENSORS[key]


def get_sensors() -> list[MotionSensor]:
  return list(_SENSORS.values())
