
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class RepositoryOwner(Entity):
    username: str
    avatar_url: str = ""
    repositories: set[str] = field(default_factory=set)

@dataclass
class User(RepositoryOwner):
    pass

@dataclass
class Organization(RepositoryOwner):
    pass

@dataclass
class UserVisit(Visit):
    username: str = ""
    contributions_last_year: int = 0
