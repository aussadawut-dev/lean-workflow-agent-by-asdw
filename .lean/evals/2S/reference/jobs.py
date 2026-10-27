import users


def mailing_list(ids):
    return [users.fetch_user(i)["email"] for i in ids if users.fetch_user(i)]
