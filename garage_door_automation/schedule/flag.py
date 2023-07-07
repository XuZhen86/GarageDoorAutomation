from absl import flags
from timezonefinder import TimezoneFinderL

LATITUDE = flags.DEFINE_float(
    name='latitude',
    default=None,
    required=True,
    help='Latitude of the current locaiton, used for calculating sunrise/sunset time.',
)
LONGITUDE = flags.DEFINE_float(
    name='longitude',
    default=None,
    required=True,
    help='Longitude of the current locaiton, used for calculating sunrise/sunset time.',
)

LOCAL_TIMEZONE_NAME = flags.DEFINE_enum(
    name='local_timezone_name',
    default=None,
    required=False,
    enum_values=TimezoneFinderL().timezone_names,
    help='Manually override local timezone name.',
)

SUNRISE_HOUR = flags.DEFINE_integer(
    name='sunrise_hour',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=23,
    help='Manually override sunrise hour instead of calculating it from the current location.',
)
SUNRISE_MINUTE = flags.DEFINE_integer(
    name='sunrise_minute',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=59,
    help='Manually override sunrise minute instead of calculating it from the current location.',
)
SUNRISE_OFFSET_MINUTES = flags.DEFINE_integer(
    name='sunrise_offset_minutes',
    default=0,
    required=False,
    lower_bound=-4 * 60,
    upper_bound=4 * 60,
    help='Advance or delay in minutes when the sunrise event is fired.',
)

SUNSET_HOUR = flags.DEFINE_integer(
    name='sunset_hour',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=23,
    help=
    'Manually override sunset hour (in local timezone) instead of calculating it from the current location.',
)
SUNSET_MINUTE = flags.DEFINE_integer(
    name='sunset_minute',
    default=None,
    required=False,
    lower_bound=0,
    upper_bound=59,
    help='Manually override sunset minute instead of calculating it from the current location.',
)
SUNSET_OFFSET_MINUTES = flags.DEFINE_integer(
    name='sunset_offset_minutes',
    default=0,
    required=False,
    lower_bound=-4 * 60,
    upper_bound=4 * 60,
    help='Advance or delay in minutes when the sunset event is fired.',
)
