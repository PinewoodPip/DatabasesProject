
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class TrendingRepo(Entity):
    owner: str
    repo: str
    stars_today: int = 0
