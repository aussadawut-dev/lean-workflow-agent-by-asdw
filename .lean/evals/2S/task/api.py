from users import fetch_usr


def get_profile(user_id):
    user = fetch_usr(user_id)
    if user is None:
        return 404, {}
    return 200, {"name": user["name"], "email": user["email"]}
