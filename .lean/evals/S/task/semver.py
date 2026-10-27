"""Semantic Versioning 2.0.0 precedence."""


def compare(a: str, b: str) -> int:
    """Return -1 if a < b, 0 if they have equal precedence, 1 if a > b (SemVer 2.0.0).

    Raise ValueError if either string is not a valid SemVer 2.0.0 version.
    """
    raise NotImplementedError
