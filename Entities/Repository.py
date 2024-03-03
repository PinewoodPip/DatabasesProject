
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class Repository(Entity):
    owner: str
    repo: str
    main_language: str = ""

@dataclass
class RepositoryVisit(Visit):
    owner: str = ""
    repo: str = ""
    forks_amount: int = 0
    commits_amount: int = 0
    # We assume main_language will not change
