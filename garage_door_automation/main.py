import asyncio

import asyncio_mqtt
from absl import app, logging

from garage_door_automation.action import to_fully_closed, to_slightly_open
from garage_door_automation.mqtt import (create_mqtt_client, process_message_loop, subscribe)
from garage_door_automation.schedule import (set_event_at_sunrise, set_event_at_sunset)


async def fully_close_at_sunrise(sunrise_event: asyncio.Event, client: asyncio_mqtt.Client) -> None:
  while True:
    logging.info('Waiting for sunrise event to be set.')
    await sunrise_event.wait()
    sunrise_event.clear()
    logging.info('Sunrise event was set, calling to_fully_closed().')
    await to_fully_closed(client)


async def slightly_open_at_sunset(sunset_event: asyncio.Event, client: asyncio_mqtt.Client) -> None:
  while True:
    logging.info('Waiting for sunset event to be set.')
    await sunset_event.wait()
    sunset_event.clear()
    logging.info('Sunset event was set, calling to_slightly_open().')
    await to_slightly_open(client)


async def main(args: list[str]) -> None:
  async with create_mqtt_client() as client:
    await subscribe(client)

    sunrise_event = asyncio.Event()
    sunset_event = asyncio.Event()

    tasks = [
        asyncio.create_task(process_message_loop(client), name='process_message_loop()'),
        asyncio.create_task(set_event_at_sunrise(sunrise_event), name='set_event_at_sunrise()'),
        asyncio.create_task(set_event_at_sunset(sunset_event), name='set_event_at_sunset()'),
        asyncio.create_task(fully_close_at_sunrise(sunrise_event, client),
                            name='fully_close_at_sunrise()'),
        asyncio.create_task(slightly_open_at_sunset(sunset_event, client),
                            name='slightly_open_at_sunset()'),
    ]
    done_tasks, pending_tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for task in pending_tasks:
      task.cancel()
    await asyncio.wait(tasks)


def app_run_main() -> None:
  app.run(lambda args: asyncio.run(main(args)))


# garage-door-automation --flagfile=data/flags.txt
