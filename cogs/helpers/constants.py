import pytz
from dateutil.relativedelta import MO, TU, WE, TH, FR, SA, SU

LOCAL_TZ = pytz.timezone('America/Chicago')

# UI Display Name -> dateutil Object mapping
WEEKDAYS = [
    (MO, "Monday"),
    (TU, "Tuesday"),
    (WE, "Wednesday"),
    (TH, "Thursday"),
    (FR, "Friday"),
    (SA, "Saturday"),
    (SU, "Sunday")
]

VALID_SPOTS = list(range(1, 34)) + list(range(41, 47))
STAFF_SPOTS = [998, 999]
GUEST_SPOTS = [46]