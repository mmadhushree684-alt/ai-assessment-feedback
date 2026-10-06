-- Run once from the backend folder: flask --app app init-db
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    username      VARCHAR(50)  NOT NULL,
    email         VARCHAR(120) NOT NULL,
    password_hash TEXT         NOT NULL,
    role          VARCHAR(10)  NOT NULL CHECK (role IN ('student', 'teacher')),
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS users_username_key ON users (LOWER(username));
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key    ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS assessments (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    created_by  INTEGER NOT NULL REFERENCES users(id),
    status      VARCHAR(10) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS questions (
    id              SERIAL PRIMARY KEY,
    assessment_id   INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_text   TEXT NOT NULL,
    question_type   VARCHAR(20) NOT NULL
                    CHECK (question_type IN ('mcq', 'short', 'sentence', 'long')),
    expected_answer TEXT,
    maximum_marks   INTEGER NOT NULL CHECK (maximum_marks > 0)
);

CREATE TABLE IF NOT EXISTS options (
    id          SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    is_correct  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS submissions (
    id                SERIAL PRIMARY KEY,
    assessment_id     INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    student_id        INTEGER NOT NULL REFERENCES users(id),
    submitted_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    total_marks       NUMERIC(6,2),
    maximum_marks     NUMERIC(6,2),
    percentage        NUMERIC(5,2),
    evaluation_status VARCHAR(12) NOT NULL DEFAULT 'pending'
                      CHECK (evaluation_status IN ('pending', 'evaluated', 'failed')),
    UNIQUE (assessment_id, student_id)
);

CREATE TABLE IF NOT EXISTS answers (
    id            SERIAL PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    question_id   INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    student_answer TEXT,
    marks         NUMERIC(6,2),
    feedback      TEXT,
    strengths     TEXT,
    improvements  TEXT
);
