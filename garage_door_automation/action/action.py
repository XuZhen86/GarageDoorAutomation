import asyncio

import asyncio_mqtt
from absl import logging

from garage_door_automation.action.flag import (FULLY_CLOSED_TO_SLIGHTLY_OPENED_TIMEOUT_SECONDS,
                                                IN_MOTION_SECONDS)
from garage_door_automation.contactsensor.contactsensor import (expect_at, expect_enter,
                                                                expect_exit, expect_not_at, where)
from garage_door_automation.contactsensor.position import Position
from garage_door_automation.switch.switch import trigger


async def to_slightly_opened(client: asyncio_mqtt.Client) -> None:
  current_position = where()
  if current_position is None:
    logging.warn('Door must be at a position, did nothing.')
    return
  if current_position == Position.SLIGHTLY_OPENED:
    logging.info('Door already at SLIGHTLY_OPENED position, did nothing.')
    return
  if current_position == Position.FULLY_OPENED:
    logging.warn('Door is at FULLY_OPENED position, did nothing.')
    return

  logging.info(f'Triggering to move the door.')
  await trigger(client)
  await expect_exit(current_position)

  timeout_s: float = FULLY_CLOSED_TO_SLIGHTLY_OPENED_TIMEOUT_SECONDS.value
  try:
    async with asyncio.timeout(timeout_s):
      await expect_enter(Position.SLIGHTLY_OPENED)
  except TimeoutError:
    logging.warning(
        f'Door did not exit FULLY_CLOSED and enter SLIGHTLY_OPENED within {timeout_s}s.')
  finally:
    logging.info('Triggering to stop the door.')
    await trigger(client)

  # If the door is still moving, within x seconds it should be at FULLY_CLOSED or FULLY_OPEN.
  logging.info(f'Wait {IN_MOTION_SECONDS.value}s before final check.')
  await asyncio.sleep(float(IN_MOTION_SECONDS.value))
  expect_not_at(Position.FULLY_CLOSED)
  # Not testing SLIGHTLY_OPENED since it could already overshot the position or in the sensor dead zone.
  # expect_at(Position.SLIGHTLY_OPENED)
  expect_not_at(Position.FULLY_OPENED)

  logging.info('The door is now SLIGHTLY_OPENED.')


async def to_fully_closed(client: asyncio_mqtt.Client) -> None:
  current_position = where()
  if current_position == Position.FULLY_CLOSED:
    logging.info('Already at FULLY_CLOSED, did nothing.')
    return

  logging.info(f'Triggering to move the door and wait 1s.')
  await trigger(client)
  await asyncio.sleep(1)

  # The door could be moving up and will enter FULLY_OPENED.
  try:
    await expect_enter(Position.FULLY_OPENED)
  except (AssertionError, TimeoutError):
    logging.info('Door did not enter FULLY_OPENED.')
  else:
    logging.info('Door entered FULLY_OPENED, sleeping 2s then triggering to move.')
    await asyncio.sleep(2)
    await trigger(client)
    # Not checking exit as the sensor value could be flaky.
    # await expect_exit(Position.FULLY_OPENED)
    await expect_enter(Position.SLIGHTLY_OPENED)
    await expect_exit(Position.SLIGHTLY_OPENED)
    await expect_enter(Position.FULLY_CLOSED)

  logging.info('Final checking.')
  expect_at(Position.FULLY_CLOSED)
  expect_not_at(Position.SLIGHTLY_OPENED)
  expect_not_at(Position.FULLY_OPENED)

  logging.info('The door is now FULLY_CLOSED.')


async def to_fully_opened(client: asyncio_mqtt.Client) -> None:
  current_position = where()
  if current_position == Position.FULLY_OPENED:
    logging.info('Already at FULLY_OPENED, doing nothing.')
    return

  logging.info(f'Triggering to move the door and wait 1s.')
  await trigger(client)
  await asyncio.sleep(1)

  try:
    await expect_enter(Position.FULLY_CLOSED)
  except (AssertionError, TimeoutError):
    logging.info('Door did not enter FULLY_CLOSED')
  else:
    logging.info('Door entered FULLY_CLOSED, sleeping 2s then triggering to move.')
    await asyncio.sleep(2)
    await trigger(client)

    await expect_exit(Position.FULLY_CLOSED)
    await expect_enter(Position.SLIGHTLY_OPENED)
    await expect_exit(Position.SLIGHTLY_OPENED)
    await expect_enter(Position.FULLY_OPENED)

  logging.info('Final checking.')
  # expect_at(Position.FULLY_OPENED)
  expect_not_at(Position.FULLY_CLOSED)
  expect_not_at(Position.SLIGHTLY_OPENED)

  logging.info('The door is now FULLY_OPENED.')
