from dataclasses import asdict, dataclass
from typing import Optional
from typing import Literal


PenStatus = Literal["candidate", "confirmed", "deleted"]
Direction = Literal["up", "down"]


@dataclass(frozen=True)
class KLine:
    symbol: str
    dt: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Pen:
    id: Optional[int]
    symbol: str
    status: PenStatus
    source: str
    start_dt: str
    end_dt: str
    start_price: float
    end_price: float
    direction: Direction

    def to_dict(self) -> dict:
        return asdict(self)
