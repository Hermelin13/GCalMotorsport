from dataclasses import dataclass
from datetime import datetime, date
import hashlib

@dataclass(frozen=True)
class RaceEvent:
    series: str
    key: str
    title: str
    start: datetime
    source: str
    all_day: date | None = None

    def __post_init__(self):
        if self.start.tzinfo is None or self.start.utcoffset() is None:
            raise ValueError(f"Event {self.key} must have a timezone-aware start")

    @property
    def stable_id(self) -> str:
        return "m" + hashlib.sha256(f"motorsport-v2:{self.series}:{self.key}".encode()).hexdigest()[:31]
