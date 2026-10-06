from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from db import get_db
from routes.auth import role_required

portal_bp = Blueprint("portal", __name__)


def teacher_assessment(cur, assessment_id):
    cur.execute("SELECT * FROM assessments WHERE id=%s AND created_by=%s", (assessment_id, session["user_id"]))
    return cur.fetchone()


@portal_bp.route("/teacher/assessments")
@role_required("teacher")
def teacher_assessments():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT a.*, COUNT(DISTINCT q.id) question_count,
                    COUNT(DISTINCT s.id) submission_count
                    FROM assessments a LEFT JOIN questions q ON q.assessment_id=a.id
                    LEFT JOIN submissions s ON s.assessment_id=a.id
                    WHERE a.created_by=%s GROUP BY a.id ORDER BY a.created_at DESC""", (session["user_id"],))
        assessments=cur.fetchall()
    return render_template("teacher/assessments.html", assessments=assessments)


@portal_bp.route("/teacher/assessment/<int:assessment_id>/edit", methods=["GET","POST"])
@role_required("teacher")
def edit_assessment(assessment_id):
    db=get_db()
    with db.cursor() as cur:
        assessment=teacher_assessment(cur, assessment_id)
    if not assessment:
        flash("Assessment not found.", "error"); return redirect(url_for("teacher.dashboard"))
    if request.method=="POST":
        title=request.form.get("title","").strip(); description=request.form.get("description","").strip()
        if not title:
            flash("Assessment title is required.","error")
        else:
            with db.cursor() as cur:
                cur.execute("UPDATE assessments SET title=%s, description=%s WHERE id=%s AND created_by=%s",(title,description,assessment_id,session["user_id"]))
            db.commit(); flash("Assessment updated.","success"); return redirect(url_for("portal.teacher_assessments"))
    return render_template("teacher/edit-assessment.html", assessment=assessment)


@portal_bp.route("/teacher/assessment/<int:assessment_id>/questions")
@role_required("teacher")
def teacher_questions(assessment_id):
    db=get_db()
    with db.cursor() as cur:
        assessment=teacher_assessment(cur,assessment_id)
        if not assessment: flash("Assessment not found.","error"); return redirect(url_for("teacher.dashboard"))
        cur.execute("""SELECT q.*, COALESCE(json_agg(json_build_object('id',o.id,'option_text',o.option_text,'is_correct',o.is_correct) ORDER BY o.id) FILTER(WHERE o.id IS NOT NULL),'[]') options
                    FROM questions q LEFT JOIN options o ON o.question_id=q.id WHERE q.assessment_id=%s GROUP BY q.id ORDER BY q.id""",(assessment_id,))
        questions=cur.fetchall()
    return render_template("teacher/questions.html",assessment=assessment,questions=questions)


@portal_bp.route("/teacher/submissions")
@role_required("teacher")
def teacher_all_submissions():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT s.*,a.title,u.name student_name,u.username FROM submissions s
                    JOIN assessments a ON a.id=s.assessment_id JOIN users u ON u.id=s.student_id
                    WHERE a.created_by=%s ORDER BY s.submitted_at DESC""",(session["user_id"],))
        submissions=cur.fetchall()
    return render_template("teacher/submissions.html",submissions=submissions,assessment=None)

@portal_bp.route("/teacher/evaluation")
@role_required("teacher")
def teacher_evaluation():
    db = get_db()

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.id,
                u.name AS student_name,
                u.username,
                a.title AS assessment_title,
                s.submitted_at,
                s.evaluation_status,
                COALESCE(s.percentage, 0) AS score_percentage
            FROM submissions s
            JOIN assessments a
                ON a.id = s.assessment_id
            JOIN users u
                ON u.id = s.student_id
            WHERE a.created_by = %s
            ORDER BY s.submitted_at DESC
            """,
            (session["user_id"],)
        )

        submissions = cur.fetchall()

    return render_template(
        "teacher/evaluation.html",
        submissions=submissions
    )


@portal_bp.route("/teacher/students")
@role_required("teacher")
def teacher_students():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT u.id,u.name,u.username,u.email,u.created_at,COUNT(s.id) submission_count
                    FROM users u LEFT JOIN submissions s ON s.student_id=u.id
                    WHERE u.role='student' GROUP BY u.id ORDER BY u.name""")
        students=cur.fetchall()
    return render_template("teacher/students.html",students=students)


@portal_bp.route("/teacher/reports")
@role_required("teacher")
def teacher_reports():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT a.title,COUNT(s.id) submissions,ROUND(AVG(s.percentage),2) average_percentage
                    FROM assessments a LEFT JOIN submissions s ON s.assessment_id=a.id
                    WHERE a.created_by=%s GROUP BY a.id ORDER BY a.created_at DESC""",(session["user_id"],))
        reports=cur.fetchall()
    return render_template("teacher/reports.html",reports=reports)


@portal_bp.route("/teacher/rubrics")
@role_required("teacher")
def teacher_rubrics():
    return render_template("teacher/rubrics.html")


@portal_bp.route("/teacher/notifications")
@role_required("teacher")
def teacher_notifications():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT s.id,s.submitted_at,a.title,u.name student_name FROM submissions s
                    JOIN assessments a ON a.id=s.assessment_id JOIN users u ON u.id=s.student_id
                    WHERE a.created_by=%s ORDER BY s.submitted_at DESC LIMIT 20""",(session["user_id"],))
        notifications=cur.fetchall()
    return render_template("teacher/notifications.html",notifications=notifications)


@portal_bp.route("/student/assessments")
@role_required("student")
def student_assessments():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT a.id,a.title,a.description,u.name teacher_name,COUNT(q.id) question_count
                    FROM assessments a JOIN users u ON u.id=a.created_by LEFT JOIN questions q ON q.assessment_id=a.id
                    WHERE a.status='published' GROUP BY a.id,u.name ORDER BY a.created_at DESC""")
        assessments=cur.fetchall()
    return render_template("student/assessments.html",assessments=assessments)


@portal_bp.route("/student/results")
@role_required("student")
def student_results():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT s.*,a.title,u.name teacher_name FROM submissions s JOIN assessments a ON a.id=s.assessment_id
                    JOIN users u ON u.id=a.created_by WHERE s.student_id=%s ORDER BY s.submitted_at DESC""",(session["user_id"],))
        results=cur.fetchall()
    return render_template("student/results.html",results=results)


@portal_bp.route("/student/result/<int:submission_id>/details")
@role_required("student")
def student_result_details(submission_id):
    db=get_db()
    with db.cursor() as cur:
        cur.execute("SELECT s.*,a.title FROM submissions s JOIN assessments a ON a.id=s.assessment_id WHERE s.id=%s AND s.student_id=%s",(submission_id,session["user_id"]))
        submission=cur.fetchone()
        if not submission: flash("Result not found.","error"); return redirect(url_for("portal.student_results"))
        cur.execute("""SELECT ans.*,q.question_text,q.question_type,q.maximum_marks FROM answers ans JOIN questions q ON q.id=ans.question_id WHERE ans.submission_id=%s ORDER BY ans.id""",(submission_id,))
        answers=cur.fetchall()
    return render_template("student/result-details.html",submission=submission,answers=answers)


@portal_bp.route("/student/performance")
@role_required("student")
def student_performance():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT COUNT(*) total,COUNT(*) FILTER(WHERE evaluation_status='evaluated') evaluated,
                    ROUND(AVG(percentage) FILTER(WHERE evaluation_status='evaluated'),2) average_percentage,
                    COALESCE(SUM(total_marks),0) total_marks FROM submissions WHERE student_id=%s""",(session["user_id"],))
        stats=cur.fetchone()
    return render_template("student/performance.html",stats=stats)


@portal_bp.route("/student/notifications")
@role_required("student")
def student_notifications():
    db=get_db()
    with db.cursor() as cur:
        cur.execute("""SELECT s.id,s.submitted_at,s.evaluation_status,a.title FROM submissions s JOIN assessments a ON a.id=s.assessment_id
                    WHERE s.student_id=%s ORDER BY s.submitted_at DESC LIMIT 20""",(session["user_id"],))
        notifications=cur.fetchall()
    return render_template("student/notifications.html",notifications=notifications)
