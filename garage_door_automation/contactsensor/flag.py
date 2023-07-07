from absl import flags

from garage_door_automation.contactsensor.position import Position

POSITIONS = flags.DEFINE_multi_enum_class(
    name='contact_sensor_positions',
    default=None,
    enum_class=Position,
    required=True,
    help='Specify the positions for the contact sensors',
)

MQTT_TOPICS = flags.DEFINE_multi_string(
    name='contact_sensor_mqtt_topics',
    default=None,
    required=True,
    help='Specify the MQTT topics for the contact sensors.',
)

NICK_NAMES = flags.DEFINE_multi_string(
    name='contact_sensor_nick_names',
    default=None,
    required=True,
    help='Specify the nick names for the contact sensors.',
)

CLOSED_WEBHOOKS = flags.DEFINE_multi_string(
    name='contact_sensor_closed_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when sensor is contacted. '
    'Use "-" if webhook for that sensor is disabled.',
)

OPENED_WEBHOOKS = flags.DEFINE_multi_string(
    name='contact_sensor_opened_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when sensor is not contacted. '
    'Use "-" if webhook for that sensor is disabled.',
)

INITIAL_STATES = flags.DEFINE_multi_integer(
    name='contact_sensor_initial_states',
    default=[-1] * len(Position),
    upper_bound=1,
    lower_bound=-1,
    help='Manually override sensor is_contact status upon startup. '
    'Should only used for testing. '
    '-1 for undefined, 0 for not contacted, 1 for contacted.',
)

STATE_VALIDITY_SECONDS = flags.DEFINE_integer(
    name='contact_sensor_state_validity_seconds',
    default=3060,
    help='Time in seconds where last reported sensor status should be valid for. '
    'This should be set to equal the sensor\'s periodic update time.',
)

EXPECT_ENTER_MAX_SECONDS = flags.DEFINE_float(
    name='expect_enter_max_seconds',
    lower_bound=0,
    upper_bound=30,
    default=15,
    help='Maximun amount of time in seconds to wait for the door to enter a position.',
)

EXPECT_EXIT_MAX_SECONDS = flags.DEFINE_float(
    name='expect_exit_max_seconds',
    lower_bound=0,
    upper_bound=30,
    default=2,
    help='Maximun amount of time in seconds to wait for the door to exit a position.',
)
