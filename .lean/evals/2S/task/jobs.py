import users


def mailing_list(ids):
    return [users.fetch_usr(i)["email"] for i in ids if users.fetch_usr(i)]
