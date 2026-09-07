import re

from django.core.exceptions import ValidationError


class SixToTwelvePasswordValidator:
    """Password policy for this project:

    * between 6 and 12 characters long
    * at least one number
    * at least one special (non alphanumeric) character
    """

    def validate(self, password, user=None):
        errors = []

        if not 6 <= len(password) <= 12:
            errors.append(
                ValidationError(
                    "This password must be between 6 and 12 characters long.",
                    code="password_length",
                )
            )
        if not re.search(r"\d", password):
            errors.append(
                ValidationError(
                    "This password must contain at least one number.",
                    code="password_no_number",
                )
            )
        if not re.search(r"[^A-Za-z0-9]", password):
            errors.append(
                ValidationError(
                    "This password must contain at least one special character.",
                    code="password_no_special",
                )
            )

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            "Your password must be 6 to 12 characters long and include at "
            "least one number and one special character."
        )
