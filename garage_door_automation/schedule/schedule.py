import asyncio
from datetime import datetime
from decimal import Decimal
from queue import Queue

from absl import logging

from garage_door_automation.schedule.datapoint import (generate_sunrise_data_point,
                                                       generate_sunset_data_point)
from garage_door_automation.schedule.util import (local_timezone, sunrise_time,
                                                  sunrise_time_with_offset, sunset_time,
                                                  sunset_time_with_offset)


async def set_event_at_sunrise(event: asyncio.Event, line_protocol_queue: Queue[str]) -> None:
  while True:
    local_timezone_ = local_timezone()

    now = datetime.now().astimezone(local_timezone_)
    sunrise_time_ = sunrise_time(now)
    sunrise_time_with_offset_ = sunrise_time_with_offset(sunrise_time_, now)
    time_till_sunrise = sunrise_time_with_offset_ - now
    seconds_till_sunrise = time_till_sunrise.total_seconds()

    logging.info(f'Local timezone is {local_timezone_}.')
    logging.info(f'Time now is {now.astimezone(local_timezone_)}.')
    logging.info(f'Sunrise time is {sunrise_time_.astimezone(local_timezone_)}.')
    logging.info(
        f'Sunrise time with offset is {sunrise_time_with_offset_.astimezone(local_timezone_)}')
    logging.info(f'Sleeping for {seconds_till_sunrise}s ({time_till_sunrise}) until sunrise.')

    local_timezone_name = None
    if local_timezone_ is not None and local_timezone_.zone is not None:
      local_timezone_name = local_timezone_.zone
    line_protocols = generate_sunrise_data_point(
        local_timezone_name, int(Decimal(sunrise_time_with_offset_.timestamp()) * (10**9)))
    for lp in line_protocols:
      line_protocol_queue.put(lp)

    await asyncio.sleep(seconds_till_sunrise)
    logging.info('Setting sunrise event.')
    event.set()

    # suntime's calculation can be tricky, like the next sunrise/sunset is within 1 minute.
    # Forcing a cooldown to avoid this issue.
    logging.info('Cooling down for 30m before calculating the next sunrise.')
    await asyncio.sleep(30 * 60)


async def set_event_at_sunset(event: asyncio.Event, line_protocol_queue: Queue[str]) -> None:
  while True:
    local_timezone_ = local_timezone()

    now = datetime.now().astimezone(local_timezone_)
    sunset_time_ = sunset_time(now)
    sunset_time_with_offset_ = sunset_time_with_offset(sunset_time_, now)
    time_till_sunset = sunset_time_with_offset_ - now
    seconds_till_sunset = time_till_sunset.total_seconds()

    logging.info(f'Local timezone is {local_timezone_}.')
    logging.info(f'Time now is {now.astimezone(local_timezone_)}.')
    logging.info(f'Sunset time is {sunset_time_.astimezone(local_timezone_)}.')
    logging.info(
        f'Sunset time with offset is {sunset_time_with_offset_.astimezone(local_timezone_)}.')
    logging.info(f'Sleeping for {seconds_till_sunset}s ({time_till_sunset}) until sunset.')

    local_timezone_name = None
    if local_timezone_ is not None and local_timezone_.zone is not None:
      local_timezone_name = local_timezone_.zone
    line_protocols = generate_sunset_data_point(
        local_timezone_name, int(Decimal(sunset_time_with_offset_.timestamp()) * (10**9)))
    for lp in line_protocols:
      line_protocol_queue.put(lp)

    await asyncio.sleep(seconds_till_sunset)
    logging.info('Setting sunset event.')
    event.set()

    # suntime's calculation can be tricky, like the next sunrise/sunset is within 1 minute.
    # Forcing a cooldown to avoid this issue.
    logging.info('Cooling down for 30m before calculating the next sunset.')
    await asyncio.sleep(30 * 60)
