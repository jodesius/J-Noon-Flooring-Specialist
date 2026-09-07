from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Project user.

    Same as Django's default user, but the email address is unique and
    required so it can be used to log in and to reset a password.
    """

    email = models.EmailField("email address", unique=True)

    # username stays the USERNAME_FIELD; email is also asked for by
    # `createsuperuser` because it is listed here.
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username
