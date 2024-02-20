import requests
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup as Soup
import re, json, os, time

COMMITS_REGEX = re.compile(r"([,\d]+) Commits$")
CONTRIBUTIONS_REGEX = re.compile(r"([,\d]+)")
URL_SUFFIX_TO_PARTS_REGEX = re.compile("\/?([^\/ ]+)\/([^\/ ]+)$")
OUTPUT_FILENAME = "output.json"

TEST_URL = "https://github.com/Norbyte/ositools"

def get_int(str, regex):
    match:str = regex.match(str).groups()[0]
    match = match.replace(",", "")
    return int(match)

def identifier(username, repo_name):
    return f"{username}/{repo_name}"

def unpack_url_suffix(suffix):
    match = URL_SUFFIX_TO_PARTS_REGEX.search(suffix)
    return match.groups()

def parse_suffixed_number(string):
    sizes_dict = {'b': 1, 'k': 1000, 'm': 1000000}
    string = string.replace(",", "").lower()
    for k, v in sizes_dict.items():
        if string[-1] == k:
            return int(float(string[:-1]) * v)

    return int(string)

@dataclass
class Exportable:
    def serialize_type(obj):
        serializable_types = set([dict, list])
        serialized_obj = obj
        if type(obj) in serializable_types:
            serialized_obj = obj
        elif type(obj) == set:
            serialized_obj = list(obj)
        elif obj is Exportable:
            serialized_obj = Exportable.serialize_type(obj)
        return serialized_obj
    
    def dict(self):
        return {k: Exportable.serialize_type(v) for k, v in asdict(self).items()}

@dataclass
class Repository(Exportable):
    user: str
    repo: str
    forks_amount: int = 0
    commits_amount: int = 0
    main_language: str = ""

@dataclass
class RepositoryOwner(Exportable):
    username: str
    repositories: set[str] = field(default_factory=set)

@dataclass
class User(RepositoryOwner):
    contributions_last_year: int = 0

@dataclass
class Organization(RepositoryOwner):
    pass

class Scraper:
    def __init__(self):
        self.repositories:dict[str, Repository] = {} # Visited repositories
        self.owners:dict[str, RepositoryOwner] = {} # Visited users
        self.queued_repositories = set() # Repositories queued for visit

    def visit_repos(self, repo_list:list[str]): # Expects a list of identifiers or URLs
        for identifier in repo_list:
            self.queue_repo(*unpack_url_suffix(identifier))

        while len(self.queued_repositories) > 0:
            username, repo_name = self.queued_repositories.pop()
            self.get_repo(username, repo_name)

        print("Queue empty; all repositories visited")
        self.export()

    def export(self):
        with open("output.json", "w") as f:
            output = {
                "repositories": {k: v.dict() for k, v in self.repositories.items()},
                "users": {k: v.dict() for k, v in self.owners.items()},
            }
            json.dump(output, f, indent=2)

    def is_repo_visited(self, username, repo_name) -> bool:
        return identifier(username, repo_name) in self.repositories
    
    def is_owner_visited(self, username) -> bool:
        return username in self.owners
    
    def get_repo(self, username:str, repo_name:str) -> Repository:
        suffix = identifier(username, repo_name)
        if self.is_repo_visited(username, repo_name):
            return self.repositories[suffix]
        
        repo = self.extract_repository(username, repo_name)
        self.repositories[suffix] = repo

        # Add the repo to the user
        user = self.get_owner(username)
        user.repositories.add(repo_name)

        return repo
    
    def queue_repo(self, username, repo):
        if not self.is_repo_visited(username, repo):
            self.queued_repositories.add((username, repo))
    
    def get_page(url) -> Soup:
        page = requests.get(url)
        soup = Soup(page.content, "html.parser")
        with open("test.html", "w") as f:
            f.write(page.text)
        return soup
    
    def get_owner(self, username) -> User:
        return self.owners[username] if username in self.owners else self.extract_owner(username)

    def extract_owner(self, username) -> RepositoryOwner:
        if self.is_owner_visited(username): return
        soup = Scraper.get_page(f"https://github.com/{username}")
        contributions_container = soup.find("div", class_="js-yearly-contributions")
        user = User(username) if contributions_container != None else Organization(username)
        
        # Get popular/pinned repositories
        container = soup.find("div", class_="js-pinned-items-reorder-container")
        form = container.find("ol", recursive=True)
        for child in form.findAll("a", recursive=True):
            href = child.attrs["href"]
            match = URL_SUFFIX_TO_PARTS_REGEX.match(href)
            if match: # Ignore links like "Repo/User/stargazers" or "Repo/User/forks"
                username, repo = match.groups()
                print("Found pinned/popular repo in user page:", username, repo)

                # Queue that repo to be visited
                self.queue_repo(username, repo)

        # Get yearly contributions
        if contributions_container != None:
            header = contributions_container.find("h2", class_="f4 text-normal mb-2", recursive=True)
            user.contributions_last_year = parse_suffixed_number(CONTRIBUTIONS_REGEX.search(header.contents[0]).group())

        self.owners[username] = user

        return user

    def extract_repository(self, username:str, repo_name:str) -> Repository:
        url_suffix = identifier(username, repo_name)
        url = f"https://github.com/{url_suffix}"
        print("Extracting", url)

        soup = Scraper.get_page(url)
        repo = Repository(username, repo_name)
        
        # Get forks amount
        forks = soup.find(href=f"/{url_suffix}/forks")
        forksLabel = forks.find("span", class_="text-bold")
        repo.forks_amount = parse_suffixed_number(forksLabel.contents[0])

        # Get commits count
        # This looks for the link to the commits, assuming the primary branch is "main" or "master"
        commits_url = None
        while commits_url == None:
            commits_url = soup.find("a", href=f"/{url_suffix}/commits/main/") or soup.find("a", href=f"/{url_suffix}/commits/master/")
            if commits_url == None: # Fetching this element is for some reason inconsistent, likely because JS is involved while loading it. Refetching the page in such case does make it work, eventually.
                soup = Scraper.get_page(url)
                time.sleep(2)
        commits = commits_url.find(string=lambda text: COMMITS_REGEX.match(text), recursive=True)
        repo.commits_amount = get_int(commits.string, COMMITS_REGEX)

        # Get primary language
        languages = soup.find("h2", class_="h4 mb-3", string="Languages")
        languages_list = languages.parent.find("ul")
        main_language = languages_list.find("li").find("a").find("span", class_="color-fg-default text-bold mr-1").contents[0]
        repo.main_language = main_language

        # Remove the repository from the visit queue
        self.queued_repositories.discard((username, repo_name))

        return repo

if __name__ == "__main__":
    scraper = Scraper()
    scraper.visit_repos([
        "PinewoodPip/EpipEncounters",
        # "https://github.com/SimpleMobileTools/Simple-Calendar"
    ])