from absl import flags

SHELLY_SWITCH_TOPIC = flags.DEFINE_string(
    name='shelly_switch_topic',
    default=None,
    required=True,
    help='A string specifying the MQTT topic for controlling the Shelly switch.',
)

SHELLY_SWITCH_DRY_RUN = flags.DEFINE_bool(
    name='shelly_switch_dry_run',
    default=True,
    required=False,
    help='If true, do not actually publish topic.',
)
