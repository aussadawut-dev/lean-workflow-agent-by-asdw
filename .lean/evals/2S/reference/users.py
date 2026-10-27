"""User lookups."""
import warnings

__all__ = ["fetch_user", "fetch_usr", "display_name"]

_USERS = {1: {"name": "Ada", "email": "ada@example.com"}, 2: {"name": "Lin", "email": "lin@example.com"}}


def fetch_user(user_id):
    """The user record for `user_id`, or None."""
    return _USERS.get(user_id)


def fetch_usr(user_id):
    """Deprecated alias of fetch_user."""
    warnings.warn("fetch_usr is deprecated; use fetch_user", DeprecationWarning, stacklevel=2)
    return fetch_user(user_id)


def display_name(user_id):
    user = fetch_user(user_id)
    return user["name"] if user else "unknown"
