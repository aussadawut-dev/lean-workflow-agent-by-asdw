from users import fetch_user


def get_profile(user_id):
    user = fetch_user(user_id)
    if user is None:
        return 404, {}
    return 200, {"name": user["name"], "email": user["email"]}
