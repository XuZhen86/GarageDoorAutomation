from datetime import datetime, timedelta

import pytz
from suntime import Sun
from timezonefinder import TimezoneFinderL

from garage_door_automation.schedule.flag import (LATITUDE, LOCAL_TIMEZONE_NAME, LONGITUDE,
                                                  SUNRISE_HOUR, SUNRISE_MINUTE,
                                                  SUNRISE_OFFSET_MINUTES, SUNSET_HOUR,
                                                  SUNSET_MINUTE, SUNSET_OFFSET_MINUTES)

_TIMEZONE_FINDER = TimezoneFinderL()


def local_timezone():
  if LOCAL_TIMEZONE_NAME.present:
    local_timezone_name = str(LOCAL_TIMEZONE_NAME.value)
  else:
    local_timezone_name = _TIMEZONE_FINDER.timezone_at(lng=float(LONGITUDE.value),
                                                       lat=float(LATITUDE.value))

  if local_timezone_name is None:
    return None
  return pytz.timezone(local_timezone_name)


def sunrise_time(now: datetime) -> datetime:
  sunrise_time = Sun(float(LATITUDE.value), float(LONGITUDE.value)).get_sunrise_time()

  if SUNRISE_HOUR.present:
    sunrise_time = sunrise_time.replace(hour=int(SUNRISE_HOUR.value), tzinfo=now.tzinfo)
  if SUNRISE_MINUTE.present:
    sunrise_time = sunrise_time.replace(minute=int(SUNRISE_MINUTE.value))

  if sunrise_time < now:
    sunrise_time += timedelta(days=1)
  return sunrise_time


def sunset_time(now: datetime) -> datetime:
  sunset_time = Sun(float(LATITUDE.value), float(LONGITUDE.value)).get_sunset_time()

  if SUNSET_HOUR.present:
    sunset_time = sunset_time.replace(hour=int(SUNSET_HOUR.value), tzinfo=now.tzinfo)
  if SUNSET_MINUTE.present:
    sunset_time = sunset_time.replace(minute=int(SUNSET_MINUTE.value))

  if sunset_time < now:
    sunset_time += timedelta(days=1)
  return sunset_time


def sunrise_time_with_offset(sunrise_time: datetime, now: datetime) -> datetime:
  sunset_time_with_offset = sunrise_time + timedelta(minutes=int(SUNRISE_OFFSET_MINUTES.value))
  if sunset_time_with_offset < now:
    sunset_time_with_offset += timedelta(days=1)

  return sunset_time_with_offset


def sunset_time_with_offset(sunset_time: datetime, now: datetime) -> datetime:
  sunset_time_with_offset = sunset_time + timedelta(minutes=int(SUNSET_OFFSET_MINUTES.value))
  if sunset_time_with_offset < now:
    sunset_time_with_offset += timedelta(days=1)

  return sunset_time_with_offset
