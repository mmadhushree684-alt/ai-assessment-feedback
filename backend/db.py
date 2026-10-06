import os

import click
import psycopg2
import psycopg2.extras
from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    """One database connection per request."""
    if "db" not in g:
        g.db = psycopg2.connect(
            current_app.config["DATABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)


@click.command("init-db")
def init_db_command():
    """Create all tables from schema.sql."""
    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
    with open(schema_path, encoding="utf-8") as f, db.cursor() as cur:
        cur.execute(f.read())
    db.commit()
    click.echo("Database tables created.")


@click.command("seed")
def seed_command():
    """Add one sample student and one sample teacher."""
    db = get_db()
    samples = [
        ("Sample Student", "Samplestudent", "sample.student@gmail.com", "Student@123", "student"),
        ("Sample Teacher", "Sampleteacher", "sample.teacher@gmail.com", "Teacher@123", "teacher"),
    ]
    with db.cursor() as cur:
        for name, username, email, password, role in samples:
            cur.execute(
                """INSERT INTO users (name, username, email, password_hash, role)
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (name, username, email, generate_password_hash(password), role),
            )
    db.commit()
    click.echo("Sample accounts added.")
