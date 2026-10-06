import io
import uuid

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Category, Note, Priority, Profile, SubTask, Task

# every widget gets the same "field-input" class so one CSS rule styles them all

INPUT = "field-input"
TEXTAREA = "field-input field-textarea"

User = get_user_model()


class UserScopedForm(forms.ModelForm):
    """
    Forms that need to know whose data they're touching. Whatever a person can
    pick in a dropdown is limited to their own things, and that limit is
    enforced here on the server too, not only by what the page happens to show.
    """

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)


class TaskForm(UserScopedForm):
    class Meta:
        model = Task
        fields = ["title", "description", "deadline", "status", "category", "priority"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Finish the quarterly report",
                "autofocus": True,
            }),
            "description": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 4,
                "placeholder": "Details (optional)",
            }),
            "deadline": forms.DateTimeInput(
                attrs={"class": INPUT, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "status": forms.Select(attrs={"class": INPUT}),
            "category": forms.Select(attrs={"class": INPUT}),
            "priority": forms.Select(attrs={"class": INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["description"].required = False
        self.fields["deadline"].required = False
        self.fields["category"].required = False
        self.fields["category"].empty_label = "No category"
        self.fields["category"].queryset = Category.objects.visible_to(self.user).order_by("name")
        self.fields["priority"].required = False
        self.fields["priority"].empty_label = "No priority"
        self.fields["priority"].queryset = Priority.objects.visible_to(self.user).order_by("name")


class SubTaskForm(UserScopedForm):
    class Meta:
        model = SubTask
        fields = ["parent_task", "title", "status"]
        widgets = {
            "parent_task": forms.Select(attrs={"class": INPUT}),
            "title": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Draft the outline", "autofocus": True,
            }),
            "status": forms.Select(attrs={"class": INPUT}),
        }
        labels = {"parent_task": "Part of"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent_task"].queryset = Task.objects.filter(owner=self.user).order_by("title")


class NoteForm(UserScopedForm):
    class Meta:
        model = Note
        fields = ["task", "content"]
        widgets = {
            "task": forms.Select(attrs={"class": INPUT}),
            "content": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 5,
                "placeholder": "Write your note here", "autofocus": True,
            }),
        }
        labels = {"task": "Attached to"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["task"].queryset = Task.objects.filter(owner=self.user).order_by("title")


class _NamedOwnedForm(UserScopedForm):
    """Shared by Category and Priority: a name that isn't already taken."""

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        taken = self._meta.model.objects.visible_to(self.user).filter(name__iexact=name)
        if self.instance.pk:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("You already have one with that name.")
        return name


class CategoryForm(_NamedOwnedForm):
    class Meta:
        model = Category
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Work", "autofocus": True,
            }),
        }


class PriorityForm(_NamedOwnedForm):
    class Meta:
        model = Priority
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. High", "autofocus": True,
            }),
        }


# ----------------------------------------------------------------
# Profile
# ----------------------------------------------------------------

AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_MAX_PIXELS = 25_000_000
AVATAR_SIZE = 320


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=150, required=False, label="First name",
        widget=forms.TextInput(attrs={"class": INPUT}),
    )
    last_name = forms.CharField(
        max_length=150, required=False, label="Last name",
        widget=forms.TextInput(attrs={"class": INPUT}),
    )
    username = forms.CharField(
        max_length=150, label="Username",
        validators=[UnicodeUsernameValidator()],
        widget=forms.TextInput(attrs={"class": INPUT, "autocomplete": "username"}),
        help_text="Letters, numbers and @/./+/-/_ only.",
    )
    remove_avatar = forms.BooleanField(required=False, label="Remove my picture")

    class Meta:
        model = Profile
        fields = ["avatar", "bio", "daily_goal", "theme"]
        widgets = {
            "avatar": forms.FileInput(attrs={
                "accept": "image/png,image/jpeg,image/webp", "class": "avatar-file",
            }),
            "bio": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 2, "maxlength": 200,
                "placeholder": "A line or two about you (optional)",
            }),
            "daily_goal": forms.NumberInput(attrs={
                "class": INPUT, "min": 1, "max": 20,
            }),
            "theme": forms.Select(attrs={"class": INPUT}),
        }
        labels = {"avatar": "Profile picture", "daily_goal": "Daily goal", "theme": "Appearance"}

    field_order = [
        "avatar", "remove_avatar", "first_name", "last_name", "username",
        "bio", "daily_goal", "theme",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance.user
        self.fields["first_name"].initial = user.first_name
        self.fields["last_name"].initial = user.last_name
        self.fields["username"].initial = user.get_username()
        self.fields["avatar"].required = False
        self.fields["bio"].required = False
        self.fields["avatar"].help_text = "PNG, JPG or WebP, up to 2 MB. It gets cropped to a square."

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        clash = User.objects.filter(username__iexact=username).exclude(pk=self.instance.user_id)
        if clash.exists():
            raise forms.ValidationError("That username is taken.")

        # The sign-up page already keeps names like "admin" or "support"
        # off the table. Renaming later shouldn't be a way around that.
        changed = username.lower() != self.instance.user.get_username().lower()
        if changed:
            if username.lower() in [n.lower() for n in settings.ACCOUNT_USERNAME_BLACKLIST]:
                raise forms.ValidationError("Please pick a different username.")
            if len(username) < settings.ACCOUNT_USERNAME_MIN_LENGTH:
                raise forms.ValidationError(
                    f"Usernames need at least {settings.ACCOUNT_USERNAME_MIN_LENGTH} characters."
                )
        return username

    def clean_avatar(self):
        upload = self.cleaned_data.get("avatar")
        # nothing new uploaded (or the box was cleared): nothing to check
        if not upload or not hasattr(upload, "content_type"):
            return upload

        if upload.size > AVATAR_MAX_BYTES:
            raise forms.ValidationError("That picture is over 2 MB. Try a smaller one.")

        try:
            upload.seek(0)
            with Image.open(upload) as probe:
                if probe.format not in ("JPEG", "PNG", "WEBP"):
                    raise forms.ValidationError("Please use a PNG, JPG or WebP picture.")
                if probe.width * probe.height > AVATAR_MAX_PIXELS:
                    raise forms.ValidationError("That picture is too large in pixels.")
                probe.verify()
        except forms.ValidationError:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
            raise forms.ValidationError("That file doesn't look like a real picture.")
        finally:
            upload.seek(0)
        return upload

    @staticmethod
    def _tidy_avatar(upload):
        """Crop to a square, drop metadata and hand back a fresh file. The
        original upload is never stored as-is, and its filename never used."""
        upload.seek(0)
        with Image.open(upload) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "transparency" in img.info else "RGB")
            img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=88)
        return ContentFile(buffer.getvalue(), name=f"{uuid.uuid4().hex}.webp")

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user

        old_avatar = None
        if self.instance.pk:
            old_avatar = Profile.objects.filter(pk=self.instance.pk).values_list("avatar", flat=True).first()

        new_upload = self.cleaned_data.get("avatar")
        fresh_upload = bool(new_upload) and hasattr(new_upload, "content_type")

        if fresh_upload:
            profile.avatar = self._tidy_avatar(new_upload)
        elif self.cleaned_data.get("remove_avatar") or new_upload is False:
            profile.avatar = ""
        else:
            profile.avatar = old_avatar or ""

        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.username = self.cleaned_data["username"]

        if commit:
            user.save()
            profile.save()
            if old_avatar and old_avatar != profile.avatar.name:
                profile.avatar.storage.delete(old_avatar)
        return profile


class DeleteAccountForm(forms.Form):
    """Asks for the password (or, for accounts that only ever signed in with
    Google/GitHub/Facebook and so have none, the username) before anything
    is deleted."""

    confirm = forms.CharField(strip=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        field = self.fields["confirm"]
        if user.has_usable_password():
            field.label = "Your password"
            field.widget = forms.PasswordInput(attrs={
                "class": INPUT, "autocomplete": "current-password", "autofocus": True,
            })
        else:
            field.label = f"Type your username ({user.get_username()}) to confirm"
            field.widget = forms.TextInput(attrs={"class": INPUT, "autofocus": True})

    def clean_confirm(self):
        value = self.cleaned_data["confirm"]
        if self.user.has_usable_password():
            if not self.user.check_password(value):
                raise forms.ValidationError("That password isn't right.")
        elif value.strip() != self.user.get_username():
            raise forms.ValidationError("That doesn't match your username.")
        return value
