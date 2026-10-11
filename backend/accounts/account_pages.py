"""Small same-origin HTML forms; GET/HEAD never consume account tokens."""

from django import forms
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods
from rest_framework.exceptions import ValidationError

from accounts.account_actions import (
    InvalidAccountLink, account_link_user, complete_password_reset, confirm_account_email,
)


class ConfirmEmailForm(forms.Form):
    uid = forms.CharField(max_length=256, widget=forms.HiddenInput)
    token = forms.CharField(max_length=256, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label="Confirm my email address")


class ResetPasswordForm(forms.Form):
    uid = forms.CharField(max_length=256, widget=forms.HiddenInput)
    token = forms.CharField(max_length=256, widget=forms.HiddenInput)
    password = forms.CharField(label="New password", strip=False, min_length=8, max_length=128,
                               widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    confirm_password = forms.CharField(label="Repeat new password", strip=False, min_length=8, max_length=128,
                                       widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))


@sensitive_variables("token", "data", "form")
def account_page(request, *, reset):
    title = "Reset your password" if reset else "Verify your email"
    form_class = ResetPasswordForm if reset else ConfirmEmailForm
    data = request.POST if request.method == "POST" else request.GET
    uid, token = data.get("uid"), data.get("token")
    try:
        account_link_user(uid, token, reset=reset)
    except InvalidAccountLink:
        return render(request, "accounts/account_action.html", {
            "title": title, "message": "This link is invalid, expired, or already used. Request a new link in the Android app.",
        }, status=400)
    form = form_class(data if request.method == "POST" else None, initial={"uid": uid, "token": token})
    if request.method == "POST" and form.is_valid():
        try:
            if reset:
                complete_password_reset(uid, token, form.cleaned_data)
            else:
                confirm_account_email(uid, token)
        except InvalidAccountLink:
            return render(request, "accounts/account_action.html", {
                "title": title, "message": "This link is invalid, expired, or already used. Request a new link in the Android app.",
            }, status=400)
        except ValidationError as exc:
            for field, errors in exc.detail.items():
                for error in errors:
                    form.add_error(field if field in form.fields else None, str(error))
        else:
            # Form action has no query string. Response has no tokens/passwords
            # and does not log the user in or require an Android deep link.
            message = "Password reset successfully." if reset else "Email verified successfully."
            return render(request, "accounts/account_action.html", {"title": title, "message": message})
    return render(request, "accounts/account_action.html", {"title": title, "form": form},
                  status=400 if request.method == "POST" else 200)


@require_http_methods(["GET", "HEAD", "POST"])
@sensitive_post_parameters("password", "confirm_password", "token", "uid")
@csrf_protect
def verify_email(request):
    return account_page(request, reset=False)


@require_http_methods(["GET", "HEAD", "POST"])
@sensitive_post_parameters("password", "confirm_password", "token", "uid")
@csrf_protect
def reset_password(request):
    return account_page(request, reset=True)
