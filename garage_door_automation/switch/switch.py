import asyncio_mqtt
from absl import logging

from garage_door_automation.switch.flag import SHELLY_SWITCH_DRY_RUN, SHELLY_SWITCH_TOPIC


async def trigger(client: asyncio_mqtt.Client, timeout_s: float = 0.25) -> None:
  logging.info(f'Publishing topic: "{SHELLY_SWITCH_TOPIC.value}", payload: "on,{timeout_s}".')

  if not bool(SHELLY_SWITCH_DRY_RUN.value):
    await client.publish(topic=str(SHELLY_SWITCH_TOPIC.value), payload=f'on,{timeout_s}')
