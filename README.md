# University of Barcelona Databases Project

This project is an analysis of public GitHub repositories, with the following objectives:

- Identify & feature open-source projects open to contributions (which GitHub itself is pretty bad at)
- Determine if there are correlations between languages used and the success of repositories
- Find out the most common styles of writing commit messages

A web crawler is used to gather data of the repositories, which is then imported into a database. The analysis is done in Python via a Jupyter Notebook, with the results being published at https://www.pinewood.team/open-source-gallery/ and https://www.pinewood.team/open-source-gallery/statistics.

Project Structure:

- `/Scraper/`: web scraper & crawler for gathering info of the repositories.
    - `/Entities/`: model classes for the data gathered; these were designed to correspond to the DB's entities from the get-go
    - `scrape.py`: main scraper script; starts out by visiting the "trending" repositories page, then explores user & topic pages to find other repositories that GitHub doesn't feature.
    - `create_csv.py`: converts `.json` data from the scraper to `.csv` for importing into the database
- `/Database/`: contains the MySQL Workbench diagram of the database's schema as well as a backup of the database with data filled in (`github.sql`).
- `/Analysis/`: contains the Jupyter Notebook which was used for the data analysis.

The [webpage of the project](https://www.pinewood.team/open-source-gallery/) offers a flexible, alternative way of browsing the open-source projects we've identified, as well as the statistics and insights we gathered from analyzing the commit messages.
