import asyncio
import aioconsole
from queue import Empty, Queue

import asyncio_mqtt
from absl import app, logging
from line_protocol_cache.asyncproducer import AsyncLineProtocolCacheProducer

from garage_door_automation.action.action import to_fully_closed, to_fully_opened, to_slightly_opened
from garage_door_automation.mqtt.mqtt import create_mqtt_client, process_message_loop, subscribe
from garage_door_automation.schedule.schedule import set_event_at_sunrise, set_event_at_sunset


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
    logging.info('Sunset event was set, calling to_slightly_opened().')
    await to_slightly_opened(client)


async def put_line_protocols(line_protocol_queue: Queue[str],
                             producer: AsyncLineProtocolCacheProducer) -> None:
  line_protocols: list[str] = []
  while True:
    try:
      line_protocols.append(line_protocol_queue.get(block=False))
    except Empty:
      await producer.put(line_protocols)
      line_protocols.clear()
      await asyncio.sleep(2)


async def main_interactive(args: list[str]) -> None:
  async with create_mqtt_client() as client:
    line_protocol_queue: Queue[str] = Queue()
    await subscribe(client)

    async def call_actions() -> None:
      while True:
        action = await aioconsole.ainput('action: ')
        print(f'{action=}')
        if action == 'to_fully_closed':
          await to_fully_closed(client)
        elif action == 'to_slightly_opened':
          await to_slightly_opened(client)
        elif action == 'to_fully_opened':
          await to_fully_opened(client)
        else:
          break

    tasks = [
        asyncio.create_task(process_message_loop(client, line_protocol_queue),
                            name='process_message_loop()'),
        asyncio.create_task(call_actions(), name='call_actions()'),
    ]
    done_tasks, pending_tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for task in pending_tasks:
      task.cancel()
    await asyncio.wait(tasks)


async def main(args: list[str]) -> None:
  logging.get_absl_handler().use_absl_log_file()  # type: ignore

  async with create_mqtt_client() as client, AsyncLineProtocolCacheProducer() as producer:
    line_protocol_queue: Queue[str] = Queue()
    await subscribe(client)

    sunrise_event = asyncio.Event()
    sunset_event = asyncio.Event()

    tasks = [
        asyncio.create_task(process_message_loop(client, line_protocol_queue),
                            name='process_message_loop()'),
        asyncio.create_task(set_event_at_sunrise(sunrise_event, line_protocol_queue),
                            name='set_event_at_sunrise()'),
        asyncio.create_task(set_event_at_sunset(sunset_event, line_protocol_queue),
                            name='set_event_at_sunset()'),
        asyncio.create_task(fully_close_at_sunrise(sunrise_event, client),
                            name='fully_close_at_sunrise()'),
        asyncio.create_task(slightly_open_at_sunset(sunset_event, client),
                            name='slightly_open_at_sunset()'),
        asyncio.create_task(put_line_protocols(line_protocol_queue, producer),
                            name='put_line_protocols()'),
    ]
    done_tasks, pending_tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for task in pending_tasks:
      task.cancel()
    await asyncio.wait(tasks)


async def dispatch_main(args: list[str]) -> None:
  if len(args) == 2 and args[1] == 'interactive':
    await main_interactive(args)
    return
  await main(args)


def app_run_main() -> None:
  app.run(lambda args: asyncio.run(dispatch_main(args), debug=True))


# garage-door-automation --flagfile=data/flags.txt
