from dateutil.relativedelta import FR, MO, SA, SU, TH, TU, WE

# UI Display Name -> dateutil Object mapping
WEEKDAYS = [
    (MO, "Monday"),
    (TU, "Tuesday"),
    (WE, "Wednesday"),
    (TH, "Thursday"),
    (FR, "Friday"),
    (SA, "Saturday"),
    (SU, "Sunday"),
]

NOON = 12