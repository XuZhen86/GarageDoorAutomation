import asyncio
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from queue import Queue

import pytz
from absl import flags, logging
from influxdb_client import Point
from suntime import Sun
from timezonefinder import TimezoneFinderL

_LATITUDE = flags.DEFINE_float(
    name='latitude',
    default=None,
    required=True,
    help='Latitude of the current locaiton, used for calculating sunrise/sunset time.',
)
_LONGITUDE = flags.DEFINE_float(
    name='longitude',
    default=None,
    required=True,
    help='Longitude of the current locaiton, used for calculating sunrise/sunset time.',
)

_TIMEZONE_FINDER = TimezoneFinderL()

_LOCAL_TIMEZONE_NAME = flags.DEFINE_enum(
    name='local_timezone_name',
    default=None,
    required=False,
    enum_values=_TIMEZONE_FINDER.timezone_names,
    help='Manually override local timezone name.',
)

_SUNRISE_HOUR = flags.DEFINE_integer(
    name='sunrise_hour',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=23,
    help='Manually override sunrise hour instead of calculating it from the current location.',
)
_SUNRISE_MINUTE = flags.DEFINE_integer(
    name='sunrise_minute',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=59,
    help='Manually override sunrise minute instead of calculating it from the current location.',
)
_SUNRISE_OFFSET_MINUTES = flags.DEFINE_integer(
    name='sunrise_offset_minutes',
    default=0,
    required=False,
    lower_bound=-4 * 60,
    upper_bound=4 * 60,
    help='Advance or delay in minutes when the sunrise event is fired.',
)

_SUNSET_HOUR = flags.DEFINE_integer(
    name='sunset_hour',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=23,
    help='Manually override sunset hour instead of calculating it from the current location.',
)
_SUNSET_MINUTE = flags.DEFINE_integer(
    name='sunset_minute',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=59,
    help='Manually override sunset minute instead of calculating it from the current location.',
)
_SUNSET_OFFSET_MINUTES = flags.DEFINE_integer(
    name='sunset_offset_minutes',
    default=0,
    required=False,
    lower_bound=-4 * 60,
    upper_bound=4 * 60,
    help='Advance or delay in minutes when the sunset event is fired.',
)


class _ScheduleDataPointType(StrEnum):
  SUNRISE = 'sunrise'
  SUNSET = 'sunset'


@dataclass(frozen=True)
class _ScheduleDataPoint:
  _type: _ScheduleDataPointType

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
    point = Point('schedule').time(
        time_ns if time_ns is not None else time.time_ns())  # type: ignore

    for key, value in asdict(self).items():
      if key.startswith('_'):
        point.tag(key[1:], value)
      else:
        point.field(key, value)

    return point.to_line_protocol()


def _local_timezone():
  if _LOCAL_TIMEZONE_NAME.present:
    local_timezone_name = str(_LOCAL_TIMEZONE_NAME.value)
  else:
    local_timezone_name = _TIMEZONE_FINDER.timezone_at(lng=_LONGITUDE.value, lat=_LATITUDE.value)

  if local_timezone_name is None:
    return None
  return pytz.timezone(local_timezone_name)


def _sunrise_time(now: datetime) -> datetime:
  sunrise_time = Sun(_LATITUDE.value, _LONGITUDE.value).get_sunrise_time()

  if _SUNRISE_HOUR.present:
    sunrise_time.replace(hour=_SUNRISE_HOUR.value)
  if _SUNRISE_MINUTE.present:
    sunrise_time.replace(minute=_SUNRISE_MINUTE.value)

  if sunrise_time < now:
    sunrise_time += timedelta(days=1)
  return sunrise_time


def _sunrise_time_with_offset(now: datetime, sunrise_time: datetime) -> datetime:
  sunset_time_with_offset = sunrise_time + timedelta(minutes=_SUNRISE_OFFSET_MINUTES.value)
  if sunset_time_with_offset < now:
    sunset_time_with_offset += timedelta(days=1)
  return sunset_time_with_offset


def _sunset_time(now: datetime) -> datetime:
  sunset_time = Sun(_LATITUDE.value, _LONGITUDE.value).get_sunset_time()

  if _SUNSET_HOUR.present:
    sunset_time.replace(hour=_SUNSET_HOUR.value)
  if _SUNSET_MINUTE.present:
    sunset_time.replace(minute=_SUNSET_MINUTE.value)

  if sunset_time < now:
    sunset_time += timedelta(days=1)
  return sunset_time


def _sunset_time_with_offset(now: datetime, sunset_time: datetime) -> datetime:
  sunset_time_with_offset = sunset_time + timedelta(minutes=_SUNSET_OFFSET_MINUTES.value)
  if sunset_time_with_offset < now:
    sunset_time_with_offset += timedelta(days=1)
  return sunset_time_with_offset


async def set_event_at_sunrise(event: asyncio.Event, line_protocol_queue: Queue[str]) -> None:
  while True:
    now = datetime.now().astimezone(timezone.utc)
    sunrise_time = _sunrise_time(now)
    sunrise_time_with_offset = _sunrise_time_with_offset(now, sunrise_time)
    time_till_sunrise = sunrise_time_with_offset - now
    seconds_till_sunrise = time_till_sunrise.total_seconds()

    local_timezone = _local_timezone()
    logging.info(f'Local timezone is {local_timezone}.')
    logging.info(f'Time now is {now.astimezone(local_timezone)}.')
    logging.info(f'Sunrise time is {sunrise_time.astimezone(local_timezone)}.')
    logging.info(
        f'Sunrise time with offset is {(sunrise_time_with_offset).astimezone(local_timezone)}')
    logging.info(f'Sleeping for {seconds_till_sunrise}s ({time_till_sunrise}) until sunrise.')

    line_protocol_queue.put(
        _ScheduleDataPoint(
            _type=_ScheduleDataPointType.SUNRISE,
            latitude=_LATITUDE.value,
            local_timezone_name=local_timezone.zone if local_timezone is not None else None,
            longitude=_LONGITUDE.value,
            sunrise_hour=_SUNRISE_HOUR.value,
            sunrise_minute=_SUNRISE_MINUTE.value,
            sunrise_offset_minutes=_SUNRISE_OFFSET_MINUTES.value,
            sunset_hour=_SUNSET_HOUR.value,
            sunset_minute=_SUNSET_MINUTE.value,
            sunset_offset_minutes=_SUNSET_OFFSET_MINUTES.value,
            timestamp_ns=int(Decimal(sunrise_time_with_offset.timestamp()) * (10**9)),
        ).to_line_protocol())

    await asyncio.sleep(seconds_till_sunrise)

    logging.info('Setting sunrise event.')
    event.set()

    # suntime's calculation can be tricky, like the next sunrise/sunset is within 1 minute.
    # Forcing a cooldown to avoid this issue.
    logging.info('Cooling down for 30m before calculating the next sunrise.')
    await asyncio.sleep(30 * 60)


async def set_event_at_sunset(event: asyncio.Event, line_protocol_queue: Queue[str]) -> None:
  while True:
    now = datetime.now().astimezone(timezone.utc)
    sunset_time = _sunset_time(now)
    sunset_time_with_offset = _sunset_time_with_offset(now, sunset_time)
    time_till_sunset = sunset_time_with_offset - now
    seconds_till_sunset = time_till_sunset.total_seconds()

    local_timezone = _local_timezone()
    logging.info(f'Local timezone is {local_timezone}.')
    logging.info(f'Time now is {now.astimezone(local_timezone)}.')
    logging.info(f'Sunset time is {sunset_time.astimezone(local_timezone)}.')
    logging.info(
        f'Sunset time with offset is {(sunset_time_with_offset).astimezone(local_timezone)}.')
    logging.info(f'Sleeping for {seconds_till_sunset}s ({time_till_sunset}) until sunset.')

    line_protocol_queue.put(
        _ScheduleDataPoint(
            _type=_ScheduleDataPointType.SUNSET,
            latitude=_LATITUDE.value,
            local_timezone_name=local_timezone.zone if local_timezone is not None else None,
            longitude=_LONGITUDE.value,
            sunrise_hour=_SUNRISE_HOUR.value,
            sunrise_minute=_SUNRISE_MINUTE.value,
            sunrise_offset_minutes=_SUNRISE_OFFSET_MINUTES.value,
            sunset_hour=_SUNSET_HOUR.value,
            sunset_minute=_SUNSET_MINUTE.value,
            sunset_offset_minutes=_SUNSET_OFFSET_MINUTES.value,
            timestamp_ns=int(Decimal(sunset_time_with_offset.timestamp()) * (10**9)),
        ).to_line_protocol())

    await asyncio.sleep(seconds_till_sunset)

    logging.info('Setting sunset event.')
    event.set()

    # suntime's calculation can be tricky, like the next sunrise/sunset is within 1 minute.
    # Forcing a cooldown to avoid this issue.
    logging.info('Cooling down for 30m before calculating the next sunset.')
    await asyncio.sleep(30 * 60)
