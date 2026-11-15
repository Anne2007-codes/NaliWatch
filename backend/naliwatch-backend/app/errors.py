class RateLimited(Exception):
    pass


class Rejected(Exception):
    """Input refused on purpose (e.g. photo shows a house interior)."""
