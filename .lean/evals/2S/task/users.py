"""User lookups."""

__all__ = ["fetch_usr", "display_name"]

_USERS = {1: {"name": "Ada", "email": "ada@example.com"}, 2: {"name": "Lin", "email": "lin@example.com"}}


def fetch_usr(user_id):
    """The user record for `user_id`, or None."""
    return _USERS.get(user_id)


def display_name(user_id):
    user = fetch_usr(user_id)
    return user["name"] if user else "unknown"
