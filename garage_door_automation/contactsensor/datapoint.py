import time
from dataclasses import asdict, dataclass
from json.decoder import JSONDecodeError

import asyncio_mqtt
from absl import logging
from influxdb_client import Point

from garage_door_automation.contactsensor.contactsensor import get_sensor
from garage_door_automation.contactsensor.position import Position
from garage_door_automation.util import get_bool, get_int, parse_payload


@dataclass(frozen=True)
class _DataPoint:
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
    point = Point('contact_sensor')
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
    is_contact = get_bool(payload, 'contact')
    link_quality = get_int(payload, 'linkquality')
    power_outage_count = get_int(payload, 'power_outage_count')
    temperature_c = get_int(payload, 'device_temperature')
    voltage_mv = get_int(payload, 'voltage')
  except (JSONDecodeError, AssertionError) as e:
    logging.exception(e)
    return []

  data_point = _DataPoint(
      _position=sensor.position,
      _mqtt_topic=sensor.mqtt_topic,
      _nick_name=sensor.nick_name,
      battery_percent=battery_percent,
      is_contact=is_contact,
      last_updated_ns=sensor.last_updated_ns,
      link_quality=link_quality,
      power_outage_count=power_outage_count,
      temperature_c=temperature_c,
      voltage_mv=voltage_mv,
  )
  return [data_point.to_line_protocol()]
