from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db
from routes.auth import role_required

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.route("/dashboard")
@role_required("student")
def dashboard():
    db = get_db()

    with db.cursor() as cur:
        cur.execute(
            """SELECT a.id, a.title, a.description, a.created_at,
                      u.name AS teacher_name,
                      COUNT(q.id) AS question_count,
                      CASE
                          WHEN EXISTS (
                              SELECT 1
                              FROM submissions s
                              WHERE s.assessment_id = a.id
                                AND s.student_id = %s
                          )
                          THEN TRUE
                          ELSE FALSE
                      END AS already_submitted
               FROM assessments a
               JOIN users u ON u.id = a.created_by
               LEFT JOIN questions q ON q.assessment_id = a.id
               WHERE a.status = 'published'
               GROUP BY a.id, u.name
               ORDER BY a.created_at DESC""",
            (session["user_id"],),
        )
        assessments = cur.fetchall()

        cur.execute(
            """SELECT s.*, a.title
               FROM submissions s
               JOIN assessments a ON a.id = s.assessment_id
               WHERE s.student_id = %s
               ORDER BY s.submitted_at DESC""",
            (session["user_id"],),
        )
        submissions = cur.fetchall()

    return render_template(
        "student/dashboard.html",
        assessments=assessments,
        submissions=submissions,
    )


@student_bp.route("/assessment/<int:assessment_id>/take", methods=["GET", "POST"])
@role_required("student")
def take_assessment(assessment_id):
    db = get_db()

    if request.method == "POST":
        with db.cursor() as cur:
            cur.execute(
                """SELECT id, title, status
                   FROM assessments
                   WHERE id = %s AND status = 'published'""",
                (assessment_id,),
            )
            assessment = cur.fetchone()

            if not assessment:
                flash("Assessment is not available.", "error")
                return redirect(url_for("student.dashboard"))

            cur.execute(
                """SELECT id
                   FROM submissions
                   WHERE assessment_id = %s AND student_id = %s""",
                (assessment_id, session["user_id"]),
            )

            if cur.fetchone():
                flash("You have already submitted this assessment.", "error")
                return redirect(url_for("student.dashboard"))

            cur.execute(
                """SELECT q.id, q.question_text, q.question_type,
                          q.expected_answer, q.maximum_marks,
                          COALESCE(
                            json_agg(
                              json_build_object(
                                'id', o.id,
                                'option_text', o.option_text
                              ) ORDER BY o.id
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

            if not questions:
                flash("This assessment has no questions.", "error")
                return redirect(url_for("student.dashboard"))

            cur.execute(
                """INSERT INTO submissions
                   (assessment_id, student_id, maximum_marks, evaluation_status)
                   VALUES (%s, %s, %s, 'pending')
                   RETURNING id""",
                (
                    assessment_id,
                    session["user_id"],
                    sum(q["maximum_marks"] for q in questions),
                ),
            )
            submission_id = cur.fetchone()["id"]

            for q in questions:
                answer = request.form.get(
                    f"question_{q['id']}", ""
                ).strip()

                cur.execute(
                    """INSERT INTO answers
                       (submission_id, question_id, student_answer)
                       VALUES (%s, %s, %s)""",
                    (submission_id, q["id"], answer),
                )

        db.commit()

        flash(
            "Assessment submitted. Your teacher can now run AI evaluation.",
            "success",
        )

        return redirect(
            url_for(
                "student.result",
                submission_id=submission_id,
            )
        )

    # GET request
    with db.cursor() as cur:

        # Check whether the student has already submitted this assessment
        cur.execute(
            """SELECT id
               FROM submissions
               WHERE assessment_id = %s AND student_id = %s""",
            (assessment_id, session["user_id"]),
        )

        existing_submission = cur.fetchone()

        if existing_submission:
            flash(
                "You have already submitted this assessment.",
                "error",
            )

            return redirect(
                url_for(
                    "student.result",
                    submission_id=existing_submission["id"],
                )
            )

        # Get assessment details
        cur.execute(
            """SELECT a.id, a.title, a.description,
                      u.name AS teacher_name
               FROM assessments a
               JOIN users u ON u.id = a.created_by
               WHERE a.id = %s
                 AND a.status = 'published'""",
            (assessment_id,),
        )

        assessment = cur.fetchone()

        if not assessment:
            flash(
                "Assessment is not available.",
                "error",
            )
            return redirect(
                url_for("student.dashboard")
            )

        # Get questions
        cur.execute(
            """SELECT q.id,
                      q.question_text,
                      q.question_type,
                      q.maximum_marks,
                      COALESCE(
                        json_agg(
                          json_build_object(
                            'id', o.id,
                            'option_text', o.option_text
                          )
                          ORDER BY o.id
                        ) FILTER (WHERE o.id IS NOT NULL),
                        '[]'
                      ) AS options
               FROM questions q
               LEFT JOIN options o
                 ON o.question_id = q.id
               WHERE q.assessment_id = %s
               GROUP BY q.id
               ORDER BY q.id""",
            (assessment_id,),
        )

        questions = cur.fetchall()

    return render_template(
        "student/take_assessment.html",
        assessment=assessment,
        questions=questions,
    )


@student_bp.route("/result/<int:submission_id>")
@role_required("student")
def result(submission_id):
    db = get_db()

    with db.cursor() as cur:
        cur.execute(
            """SELECT s.*, a.title
               FROM submissions s
               JOIN assessments a
                 ON a.id = s.assessment_id
               WHERE s.id = %s
                 AND s.student_id = %s""",
            (submission_id, session["user_id"]),
        )

        submission = cur.fetchone()

        if not submission:
            flash("Result not found.", "error")
            return redirect(
                url_for("student.dashboard")
            )

        cur.execute(
            """SELECT ans.*,
                      q.question_text,
                      q.question_type,
                      q.maximum_marks
               FROM answers ans
               JOIN questions q
                 ON q.id = ans.question_id
               WHERE ans.submission_id = %s
               ORDER BY ans.id""",
            (submission_id,),
        )

        answers = cur.fetchall()

    return render_template(
        "student/result.html",
        submission=submission,
        answers=answers,
    )