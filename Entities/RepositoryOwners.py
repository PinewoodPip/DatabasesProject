
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class RepositoryOwner(Entity):
    username: str
    repositories: set[str] = field(default_factory=set)

@dataclass
class User(RepositoryOwner):
    contributions_last_year: int = 0

@dataclass
class Organization(RepositoryOwner):
    pass