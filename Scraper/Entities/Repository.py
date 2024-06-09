
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class Repository(Entity):
    owner: str
    repo: str
    main_language: str = ""
    license: str = ""
    tags:list[str] = None
    description: str = ""
    
    def __post_init__(self):
        self.tags = [] if self.tags == None else self.tags

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
    open_pull_requests_amount: int = -1
    closed_pull_requests_amount: int = -1
    # We assume main_language will not change

@dataclass
class Commit(Entity):
    sha:str = ""
    commit_author:str = ""
    repo_owner:str = ""
    repo:str = ""
    message:str = ""
