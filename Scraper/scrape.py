import requests
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup as Soup
import re, json, os, time, io
import urllib.parse
from datetime import datetime
from utils import *
from Entities.Repository import *
from Entities.RepositoryOwners import *
from Entities.Trends import *

COMMITS_REGEX = re.compile(r"([,\d]+) Commits$")
CONTRIBUTIONS_REGEX = re.compile(r"([,\d]+)")
URL_RETURN_TO_REGEX = re.compile(r"\/login\?return_to=(.+)")
API_TOKEN = None
with open("api_token.txt", "r") as f: # Put your Personal Access Token in the file.
    API_TOKEN = f.read()

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": "Bearer " + API_TOKEN,
    "X-GitHub-Api-Version": "2022-11-28",
}

# Source: https://gist.github.com/codsane/25f0fd100b565b3fce03d4bbd7e7bf33
# Fetching this number via HTML broke sometime in March 2024. 
def commitCount(u, r):
    req = requests.get('https://api.github.com/repos/{}/{}/commits?per_page=1'.format(u, r), headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + API_TOKEN,
        "X-GitHub-Api-Version": "2022-11-28",
    })
    s = req.links['last']['url']
    s = re.search('\d+$', s).group()
    return s

class Scraper:
    # Empty string is for the "no language filter" option.
    TRENDING_PAGE_LANGUAGES = ["", "Lua", "JavaScript", "Java", "Python", "Kotlin", "C++", "C#", "C", "Rust", "TypeScript", "Clojure", "COBOL", "CoffeeScript", "CSS", "Cuda", "Cython", "Dockerfile", "ActionScript", "EJS", "Fortran", "Game Maker Language", "GDScript", "GLSL", "Gnuplot", "Go", "Gradle", "Groovy", "Haskell", "HTML", "HTTP", "Jupyter Notebook", "MATLAB", "Maven POM", "Nginx", "Ninja", "NumPy", "Papyrus", "Pascal", "PHP", "Perl", "Polar", "Prolog", "Qt Script", "R", "Ren'Py", "Sass", "Scala", "SCSS", "UnrealScript", "VHDL", "Visual Basic .Net", "Vue", "WebAssembly", "WGSL", "Witcher Script"]
    DEFAULT_TOPICS_TO_VISIT = ["nodejs", "javascript", "npm", "next", "react", "nextjs", "angular", "react-native", "vue", "mod", "unity3d", "machine-learning", "deep-learning", "emulation"]
    MAX_REPOSITORY_VISITS = 6000
    REPOSITORY_VISIT_EXPORT_INTERVAL = 50 # Determines every how many repository visits scraping data will be saved

    def __init__(self):
        self.repositories:dict[str, Repository] = {} # Visited repositories
        self.owners:dict[str, RepositoryOwner] = {} # Visited users
        self.queued_repositories = [] # Repositories queued for visit
        self.queued_owners = []
        self.topics:dict[str, Topic] = {}
        self.commits:dict[str, Commit] = {}
        self.trending = {}

        self.repository_visits:dict[str, RepositoryVisit] = {}
        self.owner_visits:dict[str, UserVisit] = {}
        self.topic_visits:dict[str, Topic] = {}

        self.topics_to_visit = [topic for topic in Scraper.DEFAULT_TOPICS_TO_VISIT]

        self.load_previous_data()

    def load_previous_data(self):
        """
            Loads data for previously-visited repositories and users,
            to queue them for a visit in this session.
        """
        if os.path.exists(os.getcwd() + "/persistence.json"):
            with open("persistence.json", "r") as f:
                data = json.load(f)
                for k, v in data["repositories"].items():
                    repo = Repository(v["owner"], v["repo"], v["main_language"], v["license"], v["tags"], v["description"])
                    self.repositories[k] = repo
                    self.queue_repo(v["owner"], v["repo"])

                    # Queue tags from previously visited repos
                    for topic in repo.tags:
                        if topic not in self.topics_to_visit and len(self.topics_to_visit) < 100:
                            print("Adding topic from repo", topic)
                            self.topics_to_visit.append(topic)
                    Scraper.MAX_REPOSITORY_VISITS += 1
                for k, v in data["owners"].items():
                    self.owners[k] = RepositoryOwner(v["username"], v["avatar_url"], set(v["repositories"]))
                    self.queue_owner(v["username"])

    def visit_owners(self):
        """
            Visits the pages of all queued users.
        """
        while len(self.queued_owners) > 0:
            username = self.queued_owners.pop(0)
            self.extract_owner(username)

        print("Queue empty; all owners visited")

    def visit_repos(self):
        """
            Visits all queued repositories.
        """
        visited_amount = 0
        while len(self.queued_repositories) > 0:
            username, repo_name = self.queued_repositories.pop(0)
            self.get_repo(username, repo_name)
            print(f"{len(self.queued_repositories)} repositories left in queue")

            visited_amount += 1
            if (visited_amount > Scraper.MAX_REPOSITORY_VISITS):
                print("Max visits reached")
                break
            elif visited_amount % Scraper.REPOSITORY_VISIT_EXPORT_INTERVAL == 0:
                self.export()

        if len(self.queued_repositories) == 0:
            print("Queue empty; all repositories visited")

    def visit_topics(self):
        """
            Visits all predefined topic pages.
        """
        for topic in self.topics_to_visit:
            self.visit_topic(topic)

        print("All topics visited")

    def visit_topic(self, topic_name:str):
        """
            Extracts information from a topic page.
        """
        soup = Scraper.get_page(f"https://github.com/topics/{topic_name}")
        topic = Topic(topic_name)
        visit = TopicVisit(name=topic_name)
        print(f"Visiting topic", topic_name)

        followers_svg = soup.find("svg", class_="octicon octicon-people mr-1")
        if followers_svg: # "Small" topics can't seem to be followed? Ex. "mod"
            followers = followers_svg.parent.contents[2]
            visit.followers = find_suffixed_number(followers)

        # Get amount of repositories
        repositories_count_header = soup.find("h2", class_="h3 color-fg-muted")
        visit.repositories = find_suffixed_number(repositories_count_header.contents[0])

        # Get the main language of the topic
        languages_dropdown = soup.find("details-menu", class_="select-menu-modal position-absolute")
        if languages_dropdown != None:
            main_language_entry = languages_dropdown.contents[3].contents[3] # First entry is "All [languages]", not useful.
            span = main_language_entry.find("span", recursive=True)
            repos_in_main_language_str = span.contents[0]
            topic.main_language = repos_in_main_language_str
        else:
            topic.main_language = ""

        # Add all top repositories from the topic to the visit queue
        articles = soup.findAll("article", class_="border rounded color-shadow-small color-bg-subtle my-4")
        for article in articles:
            header = article.find("h3")
            repo_link = header.contents[3]
            repo_identifier = repo_link.attrs["href"]
            print("Queueing repo from topic", repo_identifier)
            self.queue_repo(*unpack_url_suffix(repo_identifier))

        self.topics[topic_name] = topic
        self.topic_visits[topic_name] = visit

    def export(self):
        """
            Saves the data of all entities and visits to files.
        """
        with open("persistence.json", "w") as f:
            output = {
                "repositories": {k: v.dict() for k, v in self.repositories.items()},
                "owners": {k: v.dict() for k, v in self.owners.items()},
                "topics": {k: v.dict() for k, v in self.topics.items()},
                "commits": {k: v.dict() for k, v in self.commits.items()},
                "trending_per_language": {k: [x.dict() for x in v] for k, v in self.trending.items()},
            }
            json.dump(output, f, indent=2)

        today_str = datetime.datetime.today().strftime('%Y-%m-%d')
        if not os.path.exists("visits"):
            os.makedirs("visits")
        with open(f"visits/visit_{today_str}.json", "w") as f:
            output = {
                "repositories": {k: v.dict() for k, v in self.repository_visits.items()},
                "owners": {k: v.dict() for k, v in self.owner_visits.items()},
                "topics": {k: v.dict() for k, v in self.topic_visits.items()},
            }
            json.dump(output, f, indent=2)

    def is_repo_visited(self, username, repo_name) -> bool:
        return identifier(username, repo_name) in self.repository_visits
    
    def is_owner_visited(self, username) -> bool:
        return username in self.owner_visits
    
    def get_repo(self, username:str, repo_name:str) -> Repository:
        """
            Returns the data for a repository, visiting it if previously unvisited.
        """
        suffix = identifier(username, repo_name)
        if self.is_repo_visited(username, repo_name):
            return self.repositories[suffix]
        
        repo = self.extract_repository(username, repo_name)
        if repo != None:
            self.repositories[suffix] = repo

            # Add the repo to the user
            user = self.get_owner(username)
            user.repositories.add(repo_name)

        return repo
    
    def queue_repo(self, username, repo):
        if not self.is_repo_visited(username, repo):
            self.queued_repositories.append((username, repo))

    def queue_owner(self, username):
        if not self.is_owner_visited(username):
            self.queued_owners.append(username)
    
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
        """
            Extracts information from a user or organization page.
        """
        if self.is_owner_visited(username): return
        soup = Scraper.get_page(f"https://github.com/{username}")
        user = User(username)
        visit = UserVisit(username=username)
        
        req = requests.get(f"https://api.github.com/users/{username}", headers=HEADERS)
        if req.status_code == 200:
            json = req.json()
            user.avatar_url = json["avatar_url"]

        # Get popular/pinned repositories
        container = soup.find("div", class_="js-pinned-items-reorder-container")
        if container != None:
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
        soup = Scraper.get_page(f"https://github.com/users/{username}/contributions")
        if soup != None and soup.contents[0] != "Not Found":
            header = soup.find("h2")
            visit.contributions_last_year = parse_suffixed_number(CONTRIBUTIONS_REGEX.search(header.contents[0]).group())
        else:
            visit.contributions_last_year = -1

        self.owners[username] = user
        self.owner_visits[username] = visit

        return user

    def extract_repository(self, username:str, repo_name:str) -> Repository:
        """
            Extracts information from a repository page.
        """
        url_suffix = identifier(username, repo_name)
        url = f"https://github.com/{url_suffix}"
        print("Extracting", url)

        soup = Scraper.get_page(url)
        repo = Repository(username, repo_name)
        visit = RepositoryVisit(owner=username, repo=repo_name)
        
        req = requests.get(f"https://api.github.com/repos/{username}/{repo_name}", headers=HEADERS)
        
        # Get forks amount
        if req.status_code == 200:
            json = req.json()
            visit.forks_amount = json["forks_count"]
            visit.watchers_amount = json["subscribers_count"]
            visit.stars_amount = json["stargazers_count"]
            repo.description = json["description"]
        else:
            return # Skip the repo if the request fails (ex. 404 from deleted repos).

        # Get contributors amount
        contributors = soup.find(href=f"/{url_suffix}/graphs/contributors", class_="Link--primary no-underline Link d-flex flex-items-center") # Some repos link to this in readme, so it's best to require class matching as well.
        if contributors != None:
            contributorsLabel = contributors.find("span")
            visit.contributors_amount = parse_suffixed_number(contributorsLabel.contents[0])
        else: # Pages without the contributors section are made by only the owner.
            visit.contributors_amount = 1

        # Get license
        license_svg = soup.find("svg", class_="octicon octicon-law mr-2")
        if license_svg != None:
            parent = license_svg.parent
            license_str = parent.contents[2]
            repo.license = str.strip(license_str)

        # Get tags
        tags = soup.findAll("a", class_="topic-tag topic-tag-link")
        for tag in tags:
            repo.tags.append(str.strip(tag.contents[0]))

        # Get commit messages for newest commits
        result = requests.get(f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page=50", headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + API_TOKEN,
            "X-GitHub-Api-Version": "2022-11-28",
        })
        if result.status_code == 200:
            json = result.json()
            for commit in json:
                entry = Commit()
                sha = commit["sha"]
                msg = commit["commit"]["message"]
                author = commit["author"]["login"] if commit["author"] != None and "login" in commit["author"] else ""

                entry.sha = sha
                entry.commit_author = author
                entry.repo_owner = repo.owner
                entry.repo = repo.repo
                entry.message = msg

                self.commits[sha] = entry

        visit.commits_amount = int(commitCount(username, repo_name))

        # Get primary language
        languages = soup.find("h2", class_="h4 mb-3", string="Languages")
        if languages: # Can be none.
            languages_list = languages.parent.find("ul")
            main_language = languages_list.find("li").find("span", class_="color-fg-default text-bold mr-1", recursive=True).contents[0]
            repo.main_language = main_language

        # Fetch open & closed issues amount
        page = Scraper.get_page(f"https://github.com/{url_suffix}/issues")
        div = page.find("div", class_="table-list-header-toggle states flex-auto pl-0")
        if div != None:
            issue_links = div.findAll("a")
            open_issues = issue_links[0]
            closed_issues = issue_links[1]
            visit.open_issues_amount = get_int(open_issues.contents[2], CONTRIBUTIONS_REGEX)
            visit.closed_issues_amount = get_int(closed_issues.contents[2], CONTRIBUTIONS_REGEX)

        # Fetch open & closed PRs amount
        page = Scraper.get_page(f"https://github.com/{url_suffix}/pulls")
        div = page.find("div", class_="table-list-header-toggle states flex-auto pl-0")
        if div != None:
            issue_links = div.findAll("a")
            open_prs = issue_links[0]
            closed_prs = issue_links[1]
            visit.open_pull_requests_amount = get_int(open_prs.contents[2], CONTRIBUTIONS_REGEX)
            visit.closed_pull_requests_amount = get_int(closed_prs.contents[2], CONTRIBUTIONS_REGEX)

        # Remove the repository from the visit queue
        try:
            self.queued_repositories.remove((username, repo_name))
        except:
            pass
        self.repository_visits[identifier(username, repo_name)] = visit
        self.repositories[identifier(username, repo_name)] = repo

        return repo
    
    def visit_trending(self):
        """
            Visits all predefined languages in the trending repositories page.
        """
        for language in Scraper.TRENDING_PAGE_LANGUAGES:
            self.trending[language] = self.extract_trending(language)

    def extract_trending(self, language:str="") -> list[TrendingRepo]:
        """
            Extracts information from a trending repositories page.
        """
        language = urllib.parse.quote(language)
        soup = Scraper.get_page(f"https://github.com/trending/{language.lower()}?since=daily")
        print("Visiting trending", language)
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
                    username, repo_name = unpack_url_suffix(destination)
                    entry = TrendingRepo(owner=username, repo=repo_name)
                    self.queue_repo(username, repo_name)
                    break

            # Parse amount of new stars
            star_container = article.find("span", class_="d-inline-block float-sm-right", recursive=True)
            if star_container != None: # Somehow, repos can make it to this page with 0 stars in a day.
                star_text = star_container.contents[2]
                entry.stars_today = get_int(star_text, CONTRIBUTIONS_REGEX) # These don't seem to have a suffix.
            else:
                entry.stars_today = 0

            entries.append(entry)
            prefix = f"[{language}] " if language != "" else ""
            print(f"{prefix}{entry.owner}/{entry.repo}: {entry.stars_today} stars")

        entries = sorted(entries, key=lambda x: x.stars_today, reverse=True)

        print(len(entries), "trending repositories")

        return entries
    
    def scrape_all(self):
        """
            Performs the following:
            - Scrape all trending repos and queue them
            - Scrape all topics and queue their repositories
            - Visit all owner pages visited in previous sessions
            - Visit all repositories found from those 2 sources
                - This will visit the owners of the repositories, as well as queue their other repositories linked from user page
        """

        self.visit_trending()
        self.visit_topics()
        self.visit_owners()
        self.visit_repos()
        self.export()

if __name__ == "__main__":
    scraper = Scraper()
    print("Scraping everything...")
    scraper.scrape_all()
