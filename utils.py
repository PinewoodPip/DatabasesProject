import re

URL_SUFFIX_TO_PARTS_REGEX = re.compile("\/?([^\/ ]+)\/([^\/ ]+)$")

def get_int(str, regex):
    match:str = regex.search(str).groups()[0]
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
