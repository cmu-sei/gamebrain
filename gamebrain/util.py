from urllib.parse import urlsplit, urlunsplit


"""
The following yoinked from here:
https://codereview.stackexchange.com/questions/13027/joining-url-path-components-intelligently

Because urllib.parse.urljoin does some weird stuff.
"""
def url_path_join(*parts):
    """Normalize url parts and join them with a slash."""
    schemes, netlocs, paths, queries, fragments = zip(*(urlsplit(part) for part in parts))
    scheme, netloc, query, fragment = first_of_each(schemes, netlocs, queries, fragments)
    path = '/'.join(x.strip('/') for x in paths if x)
    return urlunsplit((scheme, netloc, path, query, fragment))

def first_of_each(*sequences):
    return (next((x for x in sequence if x), '') for sequence in sequences)
