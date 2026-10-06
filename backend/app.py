from flask import Flask, redirect, render_template, session, url_for

import db
from config import Config
from routes.auth import auth_bp
from routes.teacher import teacher_bp
from routes.student import student_bp
from routes.evaluation import evaluation_bp
from routes.portal import portal_bp


def create_app():
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
    )
    app.config.from_object(Config)
    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(portal_bp)

    @app.route("/")
    def home():
        role = session.get("role")
        if role == "teacher":
            return redirect(url_for("teacher.dashboard"))
        if role == "student":
            return redirect(url_for("student.dashboard"))
        return render_template("home.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
