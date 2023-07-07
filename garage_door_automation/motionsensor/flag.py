from absl import flags

MQTT_TOPICS = flags.DEFINE_multi_string(
    name='motion_sensor_mqtt_topics',
    default=None,
    required=True,
    help='Specify the MQTT topics for the motion sensors.',
)

NICK_NAMES = flags.DEFINE_multi_string(
    name='motion_sensor_nick_names',
    default=None,
    required=True,
    help='Specify the nick names for the motion sensors.',
)

OCCUPANCY_WEBHOOKS = flags.DEFINE_multi_string(
    name='motion_sensor_occupancy_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when occupancy is detected. '
    'Use "-" if webhook for that sensor is disabled.',
)

VACANCY_WEBHOOKS = flags.DEFINE_multi_string(
    name='motion_sensor_vacancy_webhooks',
    default=None,
    required=True,
    help='Specify the webhooks to invoke when occupancy is no longer detected. '
    'Use "-" if webhook for that sensor is disabled.',
)
