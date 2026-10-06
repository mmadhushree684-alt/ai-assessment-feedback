import hmac
from functools import wraps

import psycopg2
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from validators import validate_registration

auth_bp = Blueprint("auth", __name__)

ROLES = ("student", "teacher")


def role_required(role):
    """Protect a route by the role stored in the server-side session."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login", role=role))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@auth_bp.route("/<role>/register", methods=["GET", "POST"])
def register(role):
    if role not in ROLES:
        return redirect(url_for("home"))

    errors, form = {}, {}
    if request.method == "POST":
        form = {
            key: request.form.get(key, "").strip()
            for key in ("name", "username", "email")
        }
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = validate_registration(
            form["name"], form["username"], form["email"], password, confirm
        )

        if role == "teacher":
            entered = request.form.get("verification", "")
            expected = current_app.config["TEACHER_VERIFICATION_PASSWORD"]
            if not expected or not hmac.compare_digest(entered.encode(), expected.encode()):
                errors["verification"] = "Incorrect teacher verification password."

        if not errors:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        """INSERT INTO users
                           (name, username, email, password_hash, role)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (
                            form["name"],
                            form["username"],
                            form["email"].lower(),
                            generate_password_hash(password),
                            role,
                        ),
                    )
                db.commit()
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("auth.login", role=role))
            except psycopg2.errors.UniqueViolation:
                db.rollback()
                errors["username"] = "That username or email is already registered."

    return render_template("register.html", role=role, errors=errors, form=form)


@auth_bp.route("/<role>/login", methods=["GET", "POST"])
def login(role):
    if role not in ROLES:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db().cursor() as cur:
            cur.execute(
                """SELECT * FROM users
                   WHERE LOWER(username) = LOWER(%s) AND role = %s""",
                (username, role),
            )
            user = cur.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(
                user_id=user["id"],
                name=user["name"],
                role=user["role"],
            )
            return redirect(
                url_for(f"{role}.dashboard")
            )

        flash("Wrong username or password.", "error")

    return render_template("login.html", role=role)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))
