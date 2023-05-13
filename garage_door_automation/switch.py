import asyncio_mqtt
from absl import flags, logging

_SHELLY_SWITCH_TOPIC = flags.DEFINE_string(
    name='shelly_switch_topic',
    default=None,
    required=True,
    help='A string specifying the MQTT topic for controlling the Shelly switch.',
)

_SHELLY_SWITCH_DRY_RUN = flags.DEFINE_bool(
    name='shelly_switch_dry_run',
    default=True,
    required=False,
    help='If true, do not actually publish topic.',
)


async def trigger(client: asyncio_mqtt.Client, timeout_s: float = 0.25) -> None:
  logging.info(f'Publishing topic: "{_SHELLY_SWITCH_TOPIC.value}", payload: "on,{timeout_s}"')

  if not _SHELLY_SWITCH_DRY_RUN.value:
    await client.publish(topic=_SHELLY_SWITCH_TOPIC.value, payload=f'on,{timeout_s}')
