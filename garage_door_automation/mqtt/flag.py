from absl import flags

CLIENT_ID = flags.DEFINE_string(
    name='mqtt_client_id',
    default='styrbar-to-elgato-key-light-air',
    help='The unique client id string used when connecting to the broker.',
)

USERNAME = flags.DEFINE_string(
    name='mqtt_username',
    default=None,
    required=True,
    help='The username to authenticate with. Need have no relationship to the client id.',
)

PASSWORD = flags.DEFINE_string(
    name='mqtt_password',
    default=None,
    required=True,
    help='The password to authenticate with. Optional, set to None if not required.',
)

BROKER_ADDRESS = flags.DEFINE_string(
    name='mqtt_broker_address',
    default=None,
    required=True,
    help='The hostname or IP address of the remote broker.',
)

BROKER_PORT = flags.DEFINE_integer(
    name='mqtt_broker_port',
    default=1883,
    help='The network port of the server host to connect to.',
)
