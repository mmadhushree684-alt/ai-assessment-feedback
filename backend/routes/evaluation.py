import json
import re

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

from db import get_db
from routes.auth import role_required


evaluation_bp = Blueprint("evaluation", __name__)


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):
    """Clean and normalize text."""
    if text is None:
        return ""

    text = str(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)

    return text


# ============================================================
# MCQ EVALUATION
# MCQ is NOT evaluated by Gemini.
# ============================================================

def evaluate_mcq(student_answer, expected_answer, max_marks):
    """Evaluate MCQ using exact answer matching."""

    student = clean_text(student_answer)
    expected = clean_text(expected_answer)

    if student and student == expected:
        return (
            float(max_marks),
            "Correct answer.",
            "The selected answer matches the expected answer.",
            "No major improvement is required.",
        )

    return (
        0.0,
        "Incorrect answer.",
        "An answer was provided.",
        "Review the expected answer and related concepts.",
    )


# ============================================================
# GEMINI AI EVALUATION
# ============================================================

def evaluate_with_gemini(
    question_text,
    question_type,
    expected_answer,
    student_answer,
    max_marks,
):
    """
    Evaluate a student answer using Gemini AI.

    IMPORTANT:
    There is NO fallback word-matching evaluation here.

    If Gemini is unavailable or fails, an error is raised.
    This prevents the system from pretending that Gemini
    evaluated the answer.
    """

    api_key = current_app.config.get("GEMINI_API_KEY", "").strip()

    model_name = current_app.config.get(
        "GEMINI_MODEL",
        "gemini-3.5-flash",
    ).strip()

    # --------------------------------------------------------
    # Check API key
    # --------------------------------------------------------

    if not api_key or api_key == "YOUR_KEY_HERE":
        raise RuntimeError(
            "Gemini API key is not configured. "
            "Please add GEMINI_API_KEY to the .env file."
        )

    # --------------------------------------------------------
    # Import current Google GenAI SDK
    # --------------------------------------------------------

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "The Google GenAI SDK is not installed. "
            "Run: python -m pip install -U google-genai"
        ) from exc

    # --------------------------------------------------------
    # Create Gemini client
    # --------------------------------------------------------

    client = genai.Client(api_key=api_key)

    # --------------------------------------------------------
    # AI evaluation prompt
    # --------------------------------------------------------

    prompt = f"""
You are an AI-powered academic assessment evaluator.

Your task is to evaluate a student's answer against the
teacher-provided expected answer.

IMPORTANT:
Evaluate the MEANING and correctness of the student's answer.
Do NOT require the wording to exactly match the expected answer.

Question:
{question_text}

Question Type:
{question_type}

Teacher's Expected Answer:
{expected_answer}

Student's Answer:
{student_answer}

Maximum Marks:
{max_marks}

Evaluation rules:

1. Evaluate the MEANING, correctness, relevance, key concepts, and completeness.
2. Do NOT require the student's wording to exactly match the expected answer.
3. Do NOT give marks merely because some words are similar.
4. Give 0 marks if the answer is incorrect, irrelevant, or does not answer the question.
5. For a partially correct answer, use ONLY these fixed score levels:
   - 25% of maximum marks = very limited but relevant understanding.
   - 50% of maximum marks = partially correct, but important information is missing.
   - 75% of maximum marks = mostly correct, with only a small missing point.
   - 100% of maximum marks = completely correct and sufficiently complete.
6. Do NOT use arbitrary scores between these levels.
7. For SHORT answers, evaluate correctness, relevance, key concepts and completeness.
8. For LONG answers, evaluate correctness, relevance, key concepts, explanation,
   completeness and whether the requested example/details are provided.
9. If the question specifically asks for an example and the student does not provide
   an example, do not give 100%.
10. If the answer is correct but missing a small required detail, use 75%.
11. The marks MUST be between 0 and {max_marks}.
12. Never give more than {max_marks}.
13. Feedback must be understandable to a student.
14. Strengths must describe what the student actually did well.
15. Improvements must describe what is actually missing or incorrect.

IMPORTANT:
Calculate the marks using ONLY the fixed levels above.
Do not invent another percentage or arbitrary partial score.

Return ONLY valid JSON.

Use exactly this format:

{{
    "marks": 0,
    "feedback": "Explain the evaluation clearly.",
    "strengths": "Explain what the student did well.",
    "improvements": "Explain what the student should improve."
}}
"""

    # --------------------------------------------------------
    # Call Gemini
    # --------------------------------------------------------

    try:
        response = client.models.generate_content(
    model=model_name,
    contents=prompt,
    config={
        "temperature": 0,
    },
)

        response_text = response.text.strip()

    except Exception as exc:
        current_app.logger.exception(
            "Gemini API call failed."
        )

        raise RuntimeError(
            f"Gemini API error: {type(exc).__name__}: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Remove markdown code fences if returned
    # --------------------------------------------------------

    response_text = re.sub(
        r"^```json\s*",
        "",
        response_text,
        flags=re.IGNORECASE,
    )

    response_text = re.sub(
        r"\s*```$",
        "",
        response_text,
    )

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:

        current_app.logger.error(
            "Gemini returned invalid JSON: %s",
            response_text,
        )

        raise RuntimeError(
            "Gemini returned an invalid evaluation response."
        ) from exc

    # --------------------------------------------------------
    # Read marks
    # --------------------------------------------------------

    try:
        marks = float(data.get("marks", 0))
    except (TypeError, ValueError):

        raise RuntimeError(
            "Gemini returned an invalid marks value."
        )

    # --------------------------------------------------------
    # Keep marks within valid range
    # --------------------------------------------------------

    marks = max(
        0.0,
        min(
            marks,
            float(max_marks),
        ),
    )

    # --------------------------------------------------------
    # Read feedback
    # --------------------------------------------------------

    feedback = str(
        data.get(
            "feedback",
            "The answer has been evaluated.",
        )
    ).strip()

    strengths = str(
        data.get(
            "strengths",
            "The student attempted the question.",
        )
    ).strip()

    improvements = str(
        data.get(
            "improvements",
            "Continue reviewing the topic.",
        )
    ).strip()

    return (
        round(marks, 2),
        feedback,
        strengths,
        improvements,
    )


# ============================================================
# TEACHER - VIEW SUBMISSION
# ============================================================

@evaluation_bp.route(
    "/teacher/submission/<int:submission_id>"
)
@role_required("teacher")
def submission_detail(submission_id):

    db = get_db()

    with db.cursor() as cur:

        # ----------------------------------------------------
        # Get submission
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                s.*,
                u.name AS student_name,
                u.username AS student_username,
                u.email AS student_email,
                a.title AS assessment_title,
                a.description AS assessment_description,
                a.created_by
            FROM submissions s
            JOIN users u
                ON u.id = s.student_id
            JOIN assessments a
                ON a.id = s.assessment_id
            WHERE s.id = %s
              AND a.created_by = %s
            """,
            (
                submission_id,
                session.get("user_id"),
            ),
        )

        submission = cur.fetchone()

        if not submission:
            flash(
                "Submission not found.",
                "error",
            )

            return redirect(
                url_for("teacher.dashboard")
            )

        # ----------------------------------------------------
        # Get questions and student answers
        # ----------------------------------------------------

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
                submission["assessment_id"],
            ),
        )

        answers = cur.fetchall()

    # --------------------------------------------------------
    # Send the model name to the template
    # --------------------------------------------------------

    ai_model=current_app.config.get(
    "GEMINI_MODEL",
    "gemini-3.5-flash"
)

    return render_template(
        "teacher/submission_detail.html",
        submission=submission,
        answers=answers,
        ai_model=ai_model,
    )


# ============================================================
# TEACHER - RUN / RE-RUN AI EVALUATION
# ============================================================

@evaluation_bp.route(
    "/teacher/submission/<int:submission_id>/evaluate",
    methods=["POST"],
)
@role_required("teacher")
def evaluate(submission_id):

    db = get_db()

    try:

        with db.cursor() as cur:

            # ------------------------------------------------
            # Get submission
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    s.*,
                    a.created_by
                FROM submissions s
                JOIN assessments a
                    ON a.id = s.assessment_id
                WHERE s.id = %s
                  AND a.created_by = %s
                """,
                (
                    submission_id,
                    session.get("user_id"),
                ),
            )

            submission = cur.fetchone()

            if not submission:
                flash(
                    "Submission not found.",
                    "error",
                )

                return redirect(
                    url_for("teacher.dashboard")
                )

            # ------------------------------------------------
            # Get all answers
            # ------------------------------------------------

            cur.execute(
                """
                SELECT
                    ans.id AS answer_id,
                    ans.question_id,
                    ans.student_answer,

                    q.question_text,
                    q.question_type,
                    q.expected_answer,
                    q.maximum_marks

                FROM answers ans

                JOIN questions q
                    ON q.id = ans.question_id

                WHERE ans.submission_id = %s

                ORDER BY q.id
                """,
                (submission_id,),
            )

            answers = cur.fetchall()

            if not answers:
                flash(
                    "No answers were found for this submission.",
                    "error",
                )

                return redirect(
                    url_for(
                        "evaluation.submission_detail",
                        submission_id=submission_id,
                    )
                )

            total_marks = 0.0
            obtained_marks = 0.0

            # ------------------------------------------------
            # Evaluate every answer
            # ------------------------------------------------

            for answer in answers:

                question_type = answer["question_type"]

                question_text = answer["question_text"]

                expected_answer = answer["expected_answer"]

                student_answer = answer["student_answer"]

                maximum_marks = float(
                    answer["maximum_marks"] or 0
                )

                # --------------------------------------------
                # MCQ
                # --------------------------------------------

                if clean_text(question_type) == "mcq":

                    (
                        marks,
                        feedback,
                        strengths,
                        improvements,
                    ) = evaluate_mcq(
                        student_answer,
                        expected_answer,
                        maximum_marks,
                    )

                # --------------------------------------------
                # Text / Short / Sentence / Long
                # --------------------------------------------

                else:

                    (
                        marks,
                        feedback,
                        strengths,
                        improvements,
                    ) = evaluate_with_gemini(
                        question_text,
                        question_type,
                        expected_answer,
                        student_answer,
                        maximum_marks,
                    )

                # --------------------------------------------
                # Save evaluation
                # --------------------------------------------

                cur.execute(
                    """
                    UPDATE answers
                    SET
                        marks = %s,
                        feedback = %s,
                        strengths = %s,
                        improvements = %s
                    WHERE id = %s
                    """,
                    (
                        marks,
                        feedback,
                        strengths,
                        improvements,
                        answer["answer_id"],
                    ),
                )

                total_marks += maximum_marks

                obtained_marks += float(marks)

            # ------------------------------------------------
            # Calculate percentage
            # ------------------------------------------------

            if total_marks > 0:

                percentage = round(
                    (
                        obtained_marks
                        / total_marks
                    ) * 100,
                    2,
                )

            else:
                percentage = 0.0

            # ------------------------------------------------
            # Save final result
            # ------------------------------------------------

            cur.execute(
                """
                UPDATE submissions
                SET
                    total_marks = %s,
                    maximum_marks = %s,
                    percentage = %s,
                    evaluation_status = %s
                WHERE id = %s
                """,
                (
                    round(obtained_marks, 2),
                    round(total_marks, 2),
                    percentage,
                    "evaluated",
                    submission_id,
                ),
            )

        # ----------------------------------------------------
        # Commit only if ALL AI evaluations succeeded
        # ----------------------------------------------------

        db.commit()

        flash(
            "AI evaluation completed successfully.",
            "success",
        )

        return redirect(
            url_for(
                "evaluation.submission_detail",
                submission_id=submission_id,
            )
        )

    except Exception as exc:

        # ----------------------------------------------------
        # IMPORTANT:
        # If Gemini fails, do NOT save partial/fake results.
        # ----------------------------------------------------

        db.rollback()

        current_app.logger.exception(
            "AI evaluation failed."
        )

        flash(
            f"AI evaluation failed: {exc}",
            "error",
        )

        return redirect(
            url_for(
                "evaluation.submission_detail",
                submission_id=submission_id,
            )
        )


# ============================================================
# STUDENT RESULT
# ============================================================

@evaluation_bp.route(
    "/result/<int:submission_id>"
)
@role_required("student")
def result(submission_id):

    db = get_db()

    with db.cursor() as cur:

        # ----------------------------------------------------
        # Get submission
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                s.*,
                a.title AS assessment_title,
                a.description AS assessment_description
            FROM submissions s
            JOIN assessments a
                ON a.id = s.assessment_id
            WHERE s.id = %s
              AND s.student_id = %s
            """,
            (
                submission_id,
                session.get("user_id"),
            ),
        )

        submission = cur.fetchone()

        if not submission:
            flash(
                "Result not found.",
                "error",
            )

            return redirect(
                url_for("student.dashboard")
            )

        # ----------------------------------------------------
        # Get evaluated answers
        # ----------------------------------------------------

        cur.execute(
            """
            SELECT
                ans.id AS answer_id,
                ans.question_id,
                ans.student_answer,
                ans.marks,
                ans.feedback,
                ans.strengths,
                ans.improvements,

                q.question_text,
                q.question_type,
                q.expected_answer,
                q.maximum_marks

            FROM answers ans

            JOIN questions q
                ON q.id = ans.question_id

            WHERE ans.submission_id = %s

            ORDER BY q.id
            """,
            (submission_id,),
        )

        answers = cur.fetchall()

    return render_template(
        "student/result-details.html",
        submission=submission,
        results=answers,
    )