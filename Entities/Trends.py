
from dataclasses import dataclass, field, asdict
from .Entity import *

@dataclass
class TrendingRepo(Entity):
    owner: str
    repo: str
    stars_today: int = 0

@dataclass
class Topic(Entity):
    name: str
    main_language: str = "" # The most used language for the topic. Ex. in the case of NodeJS, it'll be JavaScript. Rarely are there multiple involved, so we don't bother storing more.
    repositories: int = 0
    followers: int = 0
