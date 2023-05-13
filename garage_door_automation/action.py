import asyncio

import asyncio_mqtt
from absl import flags, logging

from garage_door_automation.contactsensor import (Position, at, expect_at, expect_enter,
                                                  expect_exit, expect_not_at, where)
from garage_door_automation.switch import trigger

_IN_MOTION_SECONDS = flags.DEFINE_alias(
    name='in_motion_seconds',
    original_name='expect_enter_max_seconds',
)


async def to_slightly_open(client: asyncio_mqtt.Client) -> None:
  current_position = where()
  if current_position is None:
    logging.info('Door must be at a position, did nothing.')
    return
  if current_position == Position.SLIGHTLY_OPEN:
    logging.info('Door already at SLIGHTLY_OPEN position, did nothing.')
    return

  await trigger(client)
  await expect_exit(current_position)

  await expect_enter(Position.SLIGHTLY_OPEN)
  logging.info('Triggering to stop the door.')
  await trigger(client)

  # If the door is still moving, within x seconds it should be at FULLY_CLOSED or FULLY_OPEN.
  logging.info(f'Wait {_IN_MOTION_SECONDS.value}s before final check.')
  await asyncio.sleep(_IN_MOTION_SECONDS.value)
  expect_not_at(Position.FULLY_CLOSED)
  # Not testing SLIGHTLY_OPEN since it could already overshot the position or in the sensor dead zone.
  # expect_at(Position.SLIGHTLY_OPEN)
  expect_not_at(Position.FULLY_OPEN)

  logging.info('The door is now SLIGHTLY_OPEN.')


async def to_fully_closed(client: asyncio_mqtt.Client) -> None:
  current_position = where()
  if current_position == Position.FULLY_CLOSED:
    logging.info('Already at FULLY_CLOSED, did nothing.')
    return

  logging.info(f'Triggering to move the door and wait {_IN_MOTION_SECONDS.value}s.')
  await trigger(client)
  await asyncio.sleep(_IN_MOTION_SECONDS.value)

  # The door could be moving up and will enter FULLY_OPEN.
  if at(Position.FULLY_OPEN):
    logging.info(f'Triggering to move the door down.')
    await trigger(client)
    await expect_exit(Position.FULLY_OPEN)
    await expect_enter(Position.SLIGHTLY_OPEN)
    await expect_exit(Position.SLIGHTLY_OPEN)

  logging.info(f'Wait {_IN_MOTION_SECONDS.value}s before final check.')
  await asyncio.sleep(_IN_MOTION_SECONDS.value)
  expect_at(Position.FULLY_CLOSED)
  expect_not_at(Position.SLIGHTLY_OPEN)
  expect_not_at(Position.FULLY_OPEN)

  logging.info('The door is now FULLY_CLOSED.')


async def to_fully_open(client: asyncio_mqtt.Client) -> None:
  current_position = where()
  if current_position == Position.FULLY_OPEN:
    logging.info('Already at FULLY_OPEN, doing nothing.')
    return

  logging.info(f'Triggering to move the door and wait {_IN_MOTION_SECONDS.value}s.')
  await trigger(client)
  await asyncio.sleep(_IN_MOTION_SECONDS.value)

  # The door could be moving down and will enter FULLY_CLOSED.
  if at(Position.FULLY_CLOSED):
    logging.info(f'Triggering to move the door up.')
    await trigger(client)
    await expect_exit(Position.FULLY_CLOSED)
    await expect_enter(Position.SLIGHTLY_OPEN)
    await expect_exit(Position.SLIGHTLY_OPEN)

  logging.info(f'Wait {_IN_MOTION_SECONDS.value}s before final check.')
  await asyncio.sleep(_IN_MOTION_SECONDS.value)
  expect_not_at(Position.FULLY_CLOSED)
  expect_not_at(Position.SLIGHTLY_OPEN)
  expect_at(Position.FULLY_OPEN)

  logging.info('The door is now FULLY_OPEN.')
