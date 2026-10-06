"""Server-side validation. The browser checks the same rules, but the
server is the one that really enforces them."""
import re

USERNAME_RE = re.compile(r"^[A-Za-z]+$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@gmail\.com$")


def validate_registration(name, username, email, password, confirm):
    """Returns a dict of {field: message}. Empty dict means valid."""
    errors = {}

    if not name or not name.strip():
        errors["name"] = "Enter your full name."

    if not username:
        errors["username"] = "Enter a username."
    elif not USERNAME_RE.match(username):
        errors["username"] = "Use letters only (A-Z, a-z). No numbers, spaces or symbols."

    if not email:
        errors["email"] = "Enter your email."
    elif not EMAIL_RE.match(email):
        errors["email"] = "Email must end with @gmail.com (for example, student@gmail.com)."

    password_error = check_password(password)
    if password_error:
        errors["password"] = password_error

    if "password" not in errors and password != confirm:
        errors["confirm"] = "Passwords do not match."

    return errors


def check_password(password):
    if not password or len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", password):
        return "Add at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Add at least one lowercase letter."
    if not re.search(r"\d", password):
        return "Add at least one number."
    if not re.search(r"[^A-Za-z0-9]", password):
        return "Add at least one special character (for example @ or #)."
    return None
