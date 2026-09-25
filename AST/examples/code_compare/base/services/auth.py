MAX_TOKEN_AGE = 30


def valid_token(age):
    """Example policy: valid until the expiration boundary."""
    return 0 <= age < MAX_TOKEN_AGE


class LoginPolicy:
    @classmethod
    def allowed(cls, age):
        return valid_token(age)
