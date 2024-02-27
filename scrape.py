import requests
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup as Soup
import re, json, os, time
import urllib.parse
from utils import *
from Entities.Repository import *
from Entities.RepositoryOwners import *
from Entities.Trends import *

COMMITS_REGEX = re.compile(r"([,\d]+) Commits$")
CONTRIBUTIONS_REGEX = re.compile(r"([,\d]+)")
URL_RETURN_TO_REGEX = re.compile(r"\/login\?return_to=(.+)")
OUTPUT_FILENAME = "output.json"

TEST_URL = "https://github.com/Norbyte/ositools"

class Scraper:
    def __init__(self):
        self.repositories:dict[str, Repository] = {} # Visited repositories
        self.owners:dict[str, RepositoryOwner] = {} # Visited users
        self.queued_repositories = set() # Repositories queued for visit
        self.topics:dict[str, Topic] = {}

    def visit_repos(self, repo_list:list[str]): # Expects a list of identifiers or URLs
        for identifier in repo_list:
            self.queue_repo(*unpack_url_suffix(identifier))

        while len(self.queued_repositories) > 0:
            username, repo_name = self.queued_repositories.pop()
            self.get_repo(username, repo_name)

        print("Queue empty; all repositories visited")

    def visit_topics(self):
        TOPICS = ["nodejs", "javascript", "npm", "next", "react", "nextjs", "angular", "react-native", "vue", "mod"]

        for topic in TOPICS:
            self.visit_topic(topic)

        print("All topics visited, saving...")
        with open("topics.json", "w") as f:
            output = {
                "topics": {k: v.dict() for k, v in self.topics.items()},
            }
            json.dump(output, f, indent=2)

    def visit_topic(self, topic_name:str):
        soup = Scraper.get_page(f"https://github.com/topics/{topic_name}")
        topic = Topic(topic_name)
        print(f"Visiting topic", topic_name)

        followers_svg = soup.find("svg", class_="octicon octicon-people mr-1")
        if followers_svg: # "Small" topics can't seem to be followed? Ex. "mod"
            followers = followers_svg.parent.contents[2]
            topic.followers = find_suffixed_number(followers)

        # Get amount of repositories
        repositories_count_header = soup.find("h2", class_="h3 color-fg-muted")
        topic.repositories = find_suffixed_number(repositories_count_header.contents[0])

        # Get the main language of the topic
        languages_dropdown = soup.find("details-menu", class_="select-menu-modal position-absolute")
        main_language_entry = languages_dropdown.contents[3].contents[3] # First entry is "All [languages]", not useful.
        span = main_language_entry.find("span", recursive=True)
        repos_in_main_language_str = span.contents[0]
        topic.main_language = repos_in_main_language_str

        self.topics[topic_name] = topic

    def export(self):
        with open("output.json", "w") as f:
        with open(Scraper.OUTPUT_FILENAME, "w") as f:
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

        # Save the file temporarily for easier debugging (ex. to check which info is in the HTML and which is loaded via JS instead)
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
    
    def visit_trending(self):
        # Empty string is for the "no language filter" option.
        LANGUAGES = ["", "Lua", "JavaScript", "Java", "Python", "Kotlin", "C++", "C#", "C", "Rust", "TypeScript"]

        all_entries = {}
        for language in LANGUAGES:
            all_entries[language] = self.extract_trending(language)

        with open("trending.json", "w") as f:
            output = {
                "trending_per_language": {k: [x.dict() for x in v] for k, v in all_entries.items()},
            }
            json.dump(output, f, indent=2)

    def extract_trending(self, language:str="") -> list[TrendingRepo]:
        language = urllib.parse.quote(language)
        soup = Scraper.get_page(f"https://github.com/trending/{language.lower()}?since=daily")
        container = soup.find("div", {"data-hpc": True})

        entries:list[TrendingRepo] = []

        for article in container.findAll("article"):
            entry:TrendingRepo = None
            # Find the link that leads to the repository itself
            for link in article.findAll("a"):
                destination = link.attrs["href"]
                destination = urllib.parse.unquote(destination)
                if destination.startswith("/login"):
                    destination = URL_RETURN_TO_REGEX.match(destination).groups()[0]

                # A link with only 2 slashes (first and divider between user and repo) is a repo link; create the entry for it
                if str.count(destination, "/") == 2:
                    entry = TrendingRepo(*unpack_url_suffix(destination))
                    break

            # Parse amount of new stars
            star_container = article.find("span", class_="d-inline-block float-sm-right", recursive=True)
            star_text = star_container.contents[2]
            entry.stars_today = get_int(star_text, CONTRIBUTIONS_REGEX) # These don't seem to have a suffix.

            entries.append(entry)
            prefix = f"[{language}] " if language != "" else ""
            print(f"{prefix}{entry.owner}/{entry.repo}: {entry.stars_today} stars")

        entries = sorted(entries, key=lambda x: x.stars_today, reverse=True)

        print(len(entries), "trending repositories")

        return entries

if __name__ == "__main__":
    scraper = Scraper()
    # scraper.visit_repos([
    #     "PinewoodPip/EpipEncounters",
    #     # "https://github.com/SimpleMobileTools/Simple-Calendar"
    # ])
    # scraper.visit_trending()
    scraper.visit_topics()