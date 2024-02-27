
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class Repository(Entity):
    user: str
    repo: str
    forks_amount: int = 0
    commits_amount: int = 0
    main_language: str = ""
