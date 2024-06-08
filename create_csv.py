
"""
Exports all data from /visits/ to .csv files for importing into the database.
"""

import json, os
from datetime import datetime

def add_lines(lines, items, props):
    for item in items:
        line = []
        for prop in props:
            value = str(item[prop]) if prop in item else "-1"
            # Make repository descriptions default to empty string
            if prop == "description" and value == None:
                value = ""
            if prop == "description":
                value = "\"" + value + "\""
            if prop == "visit_timestamp":
                value = datetime.fromtimestamp(float(value)).strftime('%Y-%m-%d %H:%M:%S')
            line.append(value)
        lines.append(",".join(line) + "\n")

def create_csv(filename, columns, items, props):
    with open("csv/" + filename, "w") as f:
        lines = [
            ",".join(columns) + "\n", # Header
        ]
        add_lines(lines, items, props)
        f.writelines(lines)

persistence = json.load(open("persistence.json", "r"))

# Repositories
repos = [v for _,v in persistence["repositories"].items()]
create_csv("Repositories.csv", ["owner", "name", "description", "mainLanguage", "license"], repos, ["owner", "repo", "description", "main_language", "license"])

# Repository-Topic relations
repo_topic_relations = []
for repo in repos:
    for topic in repo["tags"]:
        repo_topic_relations.append({"owner": repo["owner"], "repo": repo["repo"], "topic": topic})
create_csv("RepositoryTopics.csv", ["owner", "repo", "topic"], repo_topic_relations, ["owner", "repo", "topic"])

# Commits
commits = [v for _,v in persistence["commits"].items()]
for commit in commits:
    commit["message"] = commit["message"].split("\n")[0] # Ignore description
    commit["message"] = f"'{commit['message']}'" # Wrap in quotes to prevent commas from being interpreted as field delimiters.
create_csv("Commits.csv", ["sha", "author", "repository", "repositoryOwner", "message"], commits, ["sha", "commit_author", "repo", "repo_owner", "message"])

visit_lines = {
    "RepositoryVisits": [],
}

# Visits
repos = []
owners = []
topics = []
trends = []

def parse_visit(file):
    data = json.load(file)
    repo_visits = [v for _,v in data["repositories"].items()]
    repos.extend(repo_visits)
    owner_visits = [v for _,v in data["owners"].items() if v["contributions_last_year"] > 0]
    owners.extend(owner_visits)
    topic_visits = [v for _,v in data["topics"].items()]
    topics.extend(topic_visits)

    # Older files do not have this.
    if "trending_per_language" in data:
        for lang,lang_trends in data["trending_per_language"].items():
            trends.extend(lang_trends)

for file in os.listdir("visits"):
    if file.endswith(".json") and "visit" in file:
        with open(os.path.join("visits", file), "r") as f:
            print("Parsing visit", file)
            parse_visit(f)

# Owners
owners_list = [v for _,v in persistence["owners"].items()]
owners_set = set([owner["username"] for owner in owners_list])
for visit in owners:
    if visit["username"] not in owners_set:
        owners_set.add(visit["username"])
        owners_list.append({"username": visit["username"], "avatar_url": "", "repositories": []})
for commit in persistence["commits"].values():
    if commit["commit_author"] not in owners_set:
        owners_set.add(commit["commit_author"])
        owners_list.append({"username": commit["commit_author"], "avatar_url": "", "repositories": []})
    if commit["repo_owner"] not in owners_set:
        owners_set.add(commit["repo_owner"])
        owners_list.append({"username": commit["repo_owner"], "avatar_url": "", "repositories": []})
create_csv("Owners.csv", ["username", "avatar_url"], owners_list, ["username", "avatar_url"])

# RepositoryVisits
create_csv("RepositoryVisits.csv", ["date", "owner", "name", "forks", "commits", "stars", "watchers", "contributors", "openIssues", "closedIssues", "openPullRequests", "closedPullRequests"], repos, ["visit_timestamp", "owner", "repo", "forks_amount", "commits_amount", "stars_amount", "watchers_amount", "contributors_amount", "open_issues_amount", "closed_issues_amount", "open_pull_requests", "closed_pull_requests"])

# TrendVisits
trends_json = json.load(open("trending.json", "r"))
for lang,lang_trends in trends_json["trending_per_language"].items():
    trends.extend(lang_trends)
create_csv("TrendVisits.csv", ["date", "repo_name", "owner", "starsToday"], trends, ["visit_timestamp", "repo", "owner", "stars_today"])

# TopicVisits
create_csv("TopicVisits.csv", ["date", "name", "repositories", "followers"], topics, ["visit_timestamp", "name", "repositories", "followers"])

# OwnerVisits
create_csv("OwnerVisits.csv", ["date", "username", "contributionsLastYear"], owners, ["visit_timestamp", "username", "contributions_last_year"])

# Topics
topics = [v for _,v in persistence["topics"].items()]
topics_set = set([topic["name"] for topic in topics])
with open("persistence.json", "r") as f: # Also include topics that were never visited, but are tags of repositories
    persistence = json.load(f)
    for repo in persistence["repositories"].values():
        for tag in repo["tags"]:
            if tag not in topics_set:
                topics.append({"name": tag, "main_language": ""})
                topics_set.add(tag)
# Strip whitespace
for topic in topics:
    topic["main_language"] = topic["main_language"].strip()
create_csv("Topics.csv", ["name", "mainLanguage"], topics, ["name", "main_language"])
