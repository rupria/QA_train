from services import auth
from services.auth import LoginPolicy as Policy


def login(age):
    return Policy.allowed(age)


def automatic_login(age):
    return auth.valid_token(age)


# Formatting/comment-only edit: inventory must not be an affected feature.
def open_inventory():
    return {
        "screen": "inventory",
    }
