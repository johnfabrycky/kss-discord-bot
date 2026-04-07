from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class AcademicBreak:
    name: str
    start: datetime
    end: datetime
    rotation_skip_days: int


@dataclass
class MealCalendarConfig:
    semester_start: datetime
    rotation_length_weeks: int
    breaks: List[AcademicBreak]
