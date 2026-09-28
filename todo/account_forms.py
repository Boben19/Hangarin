from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from allauth.account.forms import LoginForm, SignupForm

INPUT = "field-input"


class StyledLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["login"].widget.attrs.update({
            "class": INPUT,
            "placeholder": "Username or email",
            "autofocus": True,
        })
        self.fields["password"].widget.attrs.update({
            "class": INPUT,
            "placeholder": "Your password",
        })


class StyledSignupForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "username": "Pick a username",
            "email": "you@example.com",
            "password1": "Create a password",
            "password2": "Type it again",
        }
        for name, placeholder in placeholders.items():
            if name in self.fields:
                self.fields[name].widget.attrs.update({
                    "class": INPUT,
                    "placeholder": placeholder,
                })
        if "username" in self.fields:
            self.fields["username"].widget.attrs["autofocus"] = True


class StyledSocialSignupForm(SocialSignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("username", "email"):
            if name in self.fields:
                self.fields[name].widget.attrs.update({"class": INPUT})
