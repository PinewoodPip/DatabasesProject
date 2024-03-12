
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class Repository(Entity):
    owner: str
    repo: str
    main_language: str = ""
    license: str = ""

@dataclass
class RepositoryVisit(Visit):
    owner: str = ""
    repo: str = ""
    forks_amount: int = 0
    commits_amount: int = 0
    stars_amount: int = 0
    watchers_amount: int = 0
    contributors_amount: int = 0
    open_issues_amount: int = 0
    closed_issues_amount: int = 0
    # We assume main_language will not change
