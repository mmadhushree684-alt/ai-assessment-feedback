from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db
from routes.auth import role_required

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")


def _owned_assessment(cur, assessment_id):
    cur.execute(
        """SELECT * FROM assessments
           WHERE id = %s AND created_by = %s""",
        (assessment_id, session["user_id"]),
    )
    return cur.fetchone()


@teacher_bp.route("/dashboard")
@role_required("teacher")
def dashboard():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """SELECT a.*,
                      COUNT(DISTINCT q.id) AS question_count,
                      COUNT(DISTINCT s.id) AS submission_count
               FROM assessments a
               LEFT JOIN questions q ON q.assessment_id = a.id
               LEFT JOIN submissions s ON s.assessment_id = a.id
               WHERE a.created_by = %s
               GROUP BY a.id
               ORDER BY a.created_at DESC""",
            (session["user_id"],),
        )
        assessments = cur.fetchall()

    return render_template("teacher/dashboard.html", assessments=assessments)


@teacher_bp.route("/assessment/create", methods=["GET", "POST"])
@role_required("teacher")
def create_assessment():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Assessment title is required.", "error")
            return render_template(
                "teacher/create_assessment.html",
                title=title,
                description=description,
            )

        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO assessments
                   (title, description, created_by, status)
                   VALUES (%s, %s, %s, 'draft')
                   RETURNING id""",
                (title, description, session["user_id"]),
            )
            assessment_id = cur.fetchone()["id"]
        db.commit()

        flash("Assessment created. Now add questions.", "success")
        return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))

    return render_template("teacher/create_assessment.html", title="", description="")


@teacher_bp.route("/assessment/<int:assessment_id>/manage", methods=["GET", "POST"])
@role_required("teacher")
def manage_assessment(assessment_id):
    db = get_db()
    with db.cursor() as cur:
        assessment = _owned_assessment(cur, assessment_id)
        if not assessment:
            flash("Assessment not found.", "error")
            return redirect(url_for("teacher.dashboard"))

        cur.execute(
            """SELECT q.*,
                      COALESCE(
                        json_agg(
                          json_build_object(
                            'id', o.id,
                            'option_text', o.option_text,
                            'is_correct', o.is_correct
                          )
                          ORDER BY o.id
                        ) FILTER (WHERE o.id IS NOT NULL),
                        '[]'
                      ) AS options
               FROM questions q
               LEFT JOIN options o ON o.question_id = q.id
               WHERE q.assessment_id = %s
               GROUP BY q.id
               ORDER BY q.id""",
            (assessment_id,),
        )
        questions = cur.fetchall()

    return render_template(
        "teacher/manage_assessment.html",
        assessment=assessment,
        questions=questions,
    )


@teacher_bp.route("/assessment/<int:assessment_id>/question/add", methods=["POST"])
@role_required("teacher")
def add_question(assessment_id):
    question_text = request.form.get("question_text", "").strip()
    question_type = request.form.get("question_type", "").strip()
    expected_answer = request.form.get("expected_answer", "").strip()
    options = [request.form.get(f"option_{i}", "").strip() for i in range(1, 5)]
    correct_option = request.form.get("correct_option", "").strip()

    try:
        maximum_marks = int(request.form.get("maximum_marks", "1"))
    except ValueError:
        maximum_marks = 0

    if not question_text:
        flash("Question text is required.", "error")
        return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))

    if question_type not in ("mcq", "short", "sentence", "long"):
        flash("Choose a valid question type.", "error")
        return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))

    if maximum_marks <= 0:
        flash("Maximum marks must be greater than 0.", "error")
        return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))

    if question_type == "mcq":
        if sum(bool(x) for x in options) < 2:
            flash("MCQ needs at least two options.", "error")
            return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))
        if correct_option not in {"1", "2", "3", "4"} or not options[int(correct_option) - 1]:
            flash("Choose the correct MCQ option.", "error")
            return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))
        expected_answer = options[int(correct_option) - 1]

    db = get_db()
    with db.cursor() as cur:
        if not _owned_assessment(cur, assessment_id):
            flash("Assessment not found.", "error")
            return redirect(url_for("teacher.dashboard"))

        cur.execute(
            """INSERT INTO questions
               (assessment_id, question_text, question_type, expected_answer, maximum_marks)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id""",
            (
                assessment_id,
                question_text,
                question_type,
                expected_answer or None,
                maximum_marks,
            ),
        )
        question_id = cur.fetchone()["id"]

        if question_type == "mcq":
            for index, option_text in enumerate(options, start=1):
                if option_text:
                    cur.execute(
                        """INSERT INTO options (question_id, option_text, is_correct)
                           VALUES (%s, %s, %s)""",
                        (question_id, option_text, str(index) == correct_option),
                    )
    db.commit()

    flash("Question added.", "success")
    return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))


@teacher_bp.route("/assessment/<int:assessment_id>/question/<int:question_id>/edit", methods=["GET", "POST"])
@role_required("teacher")
def edit_question(assessment_id, question_id):
    db = get_db()

    with db.cursor() as cur:
        assessment = _owned_assessment(cur, assessment_id)
        if not assessment:
            flash("Assessment not found.", "error")
            return redirect(url_for("teacher.dashboard"))

        cur.execute(
            "SELECT * FROM questions WHERE id = %s AND assessment_id = %s",
            (question_id, assessment_id),
        )
        question = cur.fetchone()
        if not question:
            flash("Question not found.", "error")
            return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))

        cur.execute(
            """SELECT * FROM options
               WHERE question_id = %s
               ORDER BY id""",
            (question_id,),
        )
        options = cur.fetchall()

    if request.method == "POST":
        question_text = request.form.get("question_text", "").strip()
        expected_answer = request.form.get("expected_answer", "").strip()
        try:
            maximum_marks = int(request.form.get("maximum_marks", "1"))
        except ValueError:
            maximum_marks = 0

        if not question_text or maximum_marks <= 0:
            flash("Question text and a positive maximum mark are required.", "error")
            return render_template(
                "teacher/edit_question.html",
                assessment=assessment,
                question=question,
                options=options,
            )

        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """UPDATE questions
                   SET question_text = %s, expected_answer = %s, maximum_marks = %s
                   WHERE id = %s AND assessment_id = %s""",
                (
                    question_text,
                    expected_answer or None,
                    maximum_marks,
                    question_id,
                    assessment_id,
                ),
            )

            if question["question_type"] == "mcq":
                posted_options = [
                    request.form.get(f"option_{i}", "").strip()
                    for i in range(1, 5)
                ]
                correct_index = request.form.get("correct_option", "")
                if sum(bool(x) for x in posted_options) < 2:
                    flash("MCQ needs at least two options.", "error")
                    return render_template(
                        "teacher/edit_question.html",
                        assessment=assessment,
                        question=question,
                        options=options,
                    )
                if correct_index not in {"1", "2", "3", "4"} or not posted_options[int(correct_index) - 1]:
                    flash("Choose the correct MCQ option.", "error")
                    return render_template(
                        "teacher/edit_question.html",
                        assessment=assessment,
                        question=question,
                        options=options,
                    )

                cur.execute("DELETE FROM options WHERE question_id = %s", (question_id,))
                for index, option_text in enumerate(posted_options, start=1):
                    if option_text:
                        cur.execute(
                            """INSERT INTO options (question_id, option_text, is_correct)
                               VALUES (%s, %s, %s)""",
                            (question_id, option_text, str(index) == correct_index),
                        )
                cur.execute(
                    "UPDATE questions SET expected_answer = %s WHERE id = %s",
                    (posted_options[int(correct_index) - 1], question_id),
                )

        db.commit()
        flash("Question updated.", "success")
        return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))

    return render_template(
        "teacher/edit_question.html",
        assessment=assessment,
        question=question,
        options=options,
    )


@teacher_bp.route("/assessment/<int:assessment_id>/question/<int:question_id>/delete", methods=["POST"])
@role_required("teacher")
def delete_question(assessment_id, question_id):
    db = get_db()
    with db.cursor() as cur:
        if not _owned_assessment(cur, assessment_id):
            flash("Assessment not found.", "error")
            return redirect(url_for("teacher.dashboard"))
        cur.execute(
            "DELETE FROM questions WHERE id = %s AND assessment_id = %s",
            (question_id, assessment_id),
        )
    db.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))


@teacher_bp.route("/assessment/<int:assessment_id>/toggle", methods=["POST"])
@role_required("teacher")
def toggle_publish(assessment_id):
    db = get_db()
    with db.cursor() as cur:
        assessment = _owned_assessment(cur, assessment_id)
        if not assessment:
            flash("Assessment not found.", "error")
            return redirect(url_for("teacher.dashboard"))

        cur.execute(
            "SELECT COUNT(*) AS count FROM questions WHERE assessment_id = %s",
            (assessment_id,),
        )
        question_count = cur.fetchone()["count"]

        if assessment["status"] == "draft":
            if question_count == 0:
                flash("Add at least one question before publishing.", "error")
                return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))
            new_status = "published"
            message = "Assessment published. Students can now take it."
        else:
            new_status = "draft"
            message = "Assessment moved back to draft."

        cur.execute(
            "UPDATE assessments SET status = %s WHERE id = %s",
            (new_status, assessment_id),
        )
    db.commit()

    flash(message, "success")
    return redirect(url_for("teacher.manage_assessment", assessment_id=assessment_id))


@teacher_bp.route("/assessment/<int:assessment_id>/submissions")
@role_required("teacher")
def submissions(assessment_id):
    db = get_db()
    with db.cursor() as cur:
        assessment = _owned_assessment(cur, assessment_id)
        if not assessment:
            flash("Assessment not found.", "error")
            return redirect(url_for("teacher.dashboard"))

        cur.execute(
            """SELECT s.*, u.name AS student_name, u.username,
                      COALESCE(s.percentage, 0) AS score_percentage
               FROM submissions s
               JOIN users u ON u.id = s.student_id
               WHERE s.assessment_id = %s
               ORDER BY s.submitted_at DESC""",
            (assessment_id,),
        )
        submissions = cur.fetchall()

    return render_template(
        "teacher/submissions.html",
        assessment=assessment,
        submissions=submissions,
    )

@teacher_bp.route("/submission/<int:submission_id>")
@role_required("teacher")
def submission(submission_id):
    db = get_db()

    with db.cursor() as cur:
        # Get submission + student + assessment
        cur.execute(
            """
            SELECT
                s.*,
                u.name AS student_name,
                u.username AS student_username,
                a.title AS assessment_title,
                a.description AS assessment_description
            FROM submissions s
            JOIN users u ON u.id = s.student_id
            JOIN assessments a ON a.id = s.assessment_id
            WHERE s.id = %s
            """,
            (submission_id,),
        )

        submission_data = cur.fetchone()

        if not submission_data:
            flash("Submission not found.", "error")
            return redirect(url_for("teacher.dashboard"))

        # Make sure the logged-in teacher owns the assessment
        cur.execute(
            """
            SELECT *
            FROM assessments
            WHERE id = %s
              AND created_by = %s
            """,
            (
                submission_data["assessment_id"],
                session["user_id"],
            ),
        )

        assessment = cur.fetchone()

        if not assessment:
            flash("You are not authorized to view this submission.", "error")
            return redirect(url_for("teacher.dashboard"))

        # Get all questions and student answers
        cur.execute(
            """
            SELECT
                q.id AS question_id,
                q.question_text,
                q.question_type,
                q.expected_answer,
                q.maximum_marks,
                ans.id AS answer_id,
                ans.student_answer,
                ans.marks,
                ans.feedback,
                ans.strengths,
                ans.improvements
            FROM questions q
            LEFT JOIN answers ans
                ON ans.question_id = q.id
                AND ans.submission_id = %s
            WHERE q.assessment_id = %s
            ORDER BY q.id
            """,
            (
                submission_id,
                submission_data["assessment_id"],
            ),
        )

        answers = cur.fetchall()

    return render_template(
    "teacher/submission_detail.html",
    submission=submission_data,
    assessment=assessment,
    answers=answers,
)