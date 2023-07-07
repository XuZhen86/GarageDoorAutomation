from absl import flags

from garage_door_automation.contactsensor.flag import EXPECT_ENTER_MAX_SECONDS

IN_MOTION_SECONDS = flags.DEFINE_alias(
    name='in_motion_seconds',
    original_name=str(EXPECT_ENTER_MAX_SECONDS.name),
)

FULLY_CLOSED_TO_SLIGHTLY_OPENED_TIMEOUT_SECONDS = flags.DEFINE_float(
    name='fully_closed_to_slightly_opened_timeout_seconds',
    default=None,
    required=True,
    lower_bound=0,
    upper_bound=2,
    help=
    'Maximun amount of time in seconds for the door to move from FULLY_CLOSED to SLIGHTLY_OPENED.',
)
