from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Signed, time-limited token for the "verify your email" link.

    The hash includes the email address and the current verified flag, so a
    link stops working once the address is verified or changed. Expiry uses
    Django's PASSWORD_RESET_TIMEOUT setting.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email}{user.email_verified}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
