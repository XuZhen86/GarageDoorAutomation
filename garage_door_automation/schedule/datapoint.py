import time
from dataclasses import asdict, dataclass
from enum import StrEnum, unique

from influxdb_client import Point

from garage_door_automation.schedule.flag import (LATITUDE, LONGITUDE, SUNRISE_HOUR, SUNRISE_MINUTE,
                                                  SUNRISE_OFFSET_MINUTES, SUNSET_HOUR,
                                                  SUNSET_MINUTE, SUNSET_OFFSET_MINUTES)
from garage_door_automation.util import int_or_none


@unique
class _DataPointType(StrEnum):
  SUNRISE = 'sunrise'
  SUNSET = 'sunset'


@dataclass(frozen=True)
class _DataPoint:
  _type: _DataPointType

  latitude: float
  local_timezone_name: str | None
  longitude: float
  sunrise_hour: int | None
  sunrise_minute: int | None
  sunrise_offset_minutes: int
  sunset_hour: int | None
  sunset_minute: int | None
  sunset_offset_minutes: int
  timestamp_ns: int  # Timestamp of the scheduled event.

  def to_line_protocol(self, time_ns: int | None = None) -> str:
    point = Point('schedule')
    point.time(time_ns if time_ns is not None else time.time_ns())  # type: ignore

    for key, value in asdict(self).items():
      if key.startswith('_'):
        point.tag(key[1:], value)
      else:
        point.field(key, value)

    return point.to_line_protocol()


def generate_sunrise_data_point(local_timezone_name: str | None, timestamp_ns: int) -> list[str]:
  data_point = _DataPoint(
      _type=_DataPointType.SUNRISE,
      latitude=float(LATITUDE.value),
      local_timezone_name=local_timezone_name,
      longitude=float(LONGITUDE.value),
      sunrise_hour=int_or_none(SUNRISE_HOUR.value),
      sunrise_minute=int_or_none(SUNRISE_MINUTE.value),
      sunrise_offset_minutes=int(SUNRISE_OFFSET_MINUTES.value),
      sunset_hour=int_or_none(SUNSET_HOUR.value),
      sunset_minute=int_or_none(SUNSET_MINUTE.value),
      sunset_offset_minutes=int(SUNSET_OFFSET_MINUTES.value),
      timestamp_ns=timestamp_ns,
  )
  return [data_point.to_line_protocol()]


def generate_sunset_data_point(local_timezone_name: str | None, timestamp_ns: int) -> list[str]:
  data_point = _DataPoint(
      _type=_DataPointType.SUNSET,
      latitude=float(LATITUDE.value),
      local_timezone_name=local_timezone_name,
      longitude=float(LONGITUDE.value),
      sunrise_hour=int_or_none(SUNRISE_HOUR.value),
      sunrise_minute=int_or_none(SUNRISE_MINUTE.value),
      sunrise_offset_minutes=int(SUNRISE_OFFSET_MINUTES.value),
      sunset_hour=int_or_none(SUNSET_HOUR.value),
      sunset_minute=int_or_none(SUNSET_MINUTE.value),
      sunset_offset_minutes=int(SUNSET_OFFSET_MINUTES.value),
      timestamp_ns=timestamp_ns,
  )
  return [data_point.to_line_protocol()]
