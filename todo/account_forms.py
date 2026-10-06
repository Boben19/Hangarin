from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from allauth.account.forms import LoginForm, SignupForm

INPUT = "field-input"


class ErrorAwareMixin:
    """
    Marks every field that failed validation so screen readers announce it
    and the page can style it, and ties the field to the message under it
    (the template writes the message with the id "<field id>-err").
    """

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["aria-invalid"] = "true"
                widget.attrs["aria-describedby"] = f"{self[name].id_for_label}-err"


class StyledLoginForm(ErrorAwareMixin, LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No autofocus attribute on purpose: on a phone it throws the
        # keyboard up over the page before anyone has read it. app.js focuses
        # the first field on devices with a real pointer instead.
        self.fields["login"].widget.attrs.update({
            "class": INPUT,
            "placeholder": "Username or email",
            "autocapitalize": "none",
            "spellcheck": "false",
        })
        self.fields["password"].widget.attrs.update({
            "class": INPUT,
            "placeholder": "Password",
        })


class StyledSignupForm(ErrorAwareMixin, SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "username": "Choose a username",
            "email": "you@example.com",
            "password1": "At least 10 characters",
            "password2": "Type it again",
        }
        for name, placeholder in placeholders.items():
            if name in self.fields:
                self.fields[name].widget.attrs.update({
                    "class": INPUT,
                    "placeholder": placeholder,
                })
        if "username" in self.fields:
            self.fields["username"].widget.attrs.update({
                "autocapitalize": "none",
                "spellcheck": "false",
            })


class StyledSocialSignupForm(ErrorAwareMixin, SocialSignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("username", "email"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({"class": INPUT})
