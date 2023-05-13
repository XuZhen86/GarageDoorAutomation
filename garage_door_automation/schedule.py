import asyncio
from datetime import datetime, timedelta, timezone

import pytz
from absl import flags, logging
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
    default=0,
    required=False,
    lower_bound=0,
    upper_bound=59,
    help='Manually override sunrise minute instead of calculating it from the current location.',
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
    default=0,
    required=False,
    lower_bound=0,
    upper_bound=59,
    help='Manually override sunset minute instead of calculating it from the current location.',
)


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
    sunrise_time.replace(hour=_SUNRISE_HOUR.value, minute=_SUNRISE_MINUTE.value)
  if sunrise_time < now:
    sunrise_time += timedelta(days=1)
  return sunrise_time


def _sunset_time(now: datetime) -> datetime:
  sunset_time = Sun(_LATITUDE.value, _LONGITUDE.value).get_sunset_time()
  if _SUNSET_HOUR.present:
    sunset_time.replace(hour=_SUNSET_HOUR.value, minute=_SUNSET_MINUTE.value)
  if sunset_time < now:
    sunset_time += timedelta(days=1)
  return sunset_time


async def set_event_at_sunrise(event: asyncio.Event) -> None:
  while True:
    now = datetime.now().astimezone(timezone.utc)
    sunrise_time = _sunrise_time(now)
    time_till_sunrise = sunrise_time - now
    seconds_till_sunrise = time_till_sunrise.total_seconds()

    local_timezone = _local_timezone()
    logging.info(f'Local timezone is {local_timezone}.')
    logging.info(f'Time now is {now.astimezone(local_timezone)}.')
    logging.info(f'Sunrise time is {sunrise_time.astimezone(local_timezone)}.')
    logging.info(f'Sleeping for {seconds_till_sunrise}s ({time_till_sunrise}) until sunrise.')

    await asyncio.sleep(seconds_till_sunrise)
    event.set()
    logging.info('Sunrise event was set.')


async def set_event_at_sunset(event: asyncio.Event) -> None:
  while True:
    now = datetime.now().astimezone(timezone.utc)
    sunset_time = _sunset_time(now)
    time_till_sunset = sunset_time - now
    seconds_till_sunset = time_till_sunset.total_seconds()

    local_timezone = _local_timezone()
    logging.info(f'Local timezone is {local_timezone}.')
    logging.info(f'Time now is {now.astimezone(local_timezone)}.')
    logging.info(f'Sunset time is {sunset_time.astimezone(local_timezone)}.')
    logging.info(f'Sleeping for {seconds_till_sunset}s ({time_till_sunset}) until sunset.')

    await asyncio.sleep(seconds_till_sunset)
    event.set()
    logging.info('Sunset event was set.')
