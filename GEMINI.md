# AI-Based Keystroke Dynamics Data Collection Platform

## Role
You are an expert full-stack software engineer and data scientist. Build a research-grade web platform to collect programming-based keystroke dynamics for continuous user authentication.

## Core Priorities
- **High-Resolution Timing:** Sub-millisecond accuracy using `performance.now()` is non-negotiable.
- **Privacy:** Strict anonymization of participant data.
- **Performance:** Non-blocking UI; the logger must not interfere with the user's typing rhythm.

---

# Participant & Privacy Framework

### Identification
- Participants register via **Matriculation Number** and **Password**.
- **Security:** The raw matric number must NEVER be stored. Use a salted hash (bcrypt/Argon2) for both the matric number and password.
- **Anonymization:** Create a unique `participant_id` (UUID) to link data. The research dataset must only reference this UUID.

### Ethical Compliance
- Present a mandatory **Consent Form** before registration.
- Explain data usage, anonymization, and the voluntary nature of the study.

---

# Data Collection Engine

### Logging Logic
Attach event listeners for `keydown` and `keyup` on the code editor.
- **Required Fields:** `session_id`, `key`, `event_type`, `timestamp` (using `performance.now()`), `cursor_position`, `text_length`, `is_auto_repeat`.
- **Target Keys:** Alphanumerics AND programming symbols `{ } ( ) [ ] ; : < > = / \ _`.

### Performance Batching
- Buffer events locally in the React state.
- POST to the backend every **2 seconds** or **50 events** to avoid UI lag.

---

# Technical Architecture

### Backend (FastAPI + PostgreSQL)
Strictly implement the following normalized relational schema:
- **Table `users`:** `user_id` (UUID), `matric_hash`, `password_hash`, `created_at`.
- **Table `participants`:** `participant_id` (UUID), `user_id` (FK), `device_type`, `keyboard_layout`, `os`.
- **Table `programming_tasks`:** `task_id`, `task_title`, `description`, `difficulty_level`, `expected_solution_length`.
- **Table `sessions`:** `session_id`, `participant_id` (FK), `task_id` (FK), `start_time`, `end_time`, `total_keystrokes`.
- **Table `keystroke_events`:** `event_id`, `session_id` (FK), `key`, `event_type`, `timestamp`, `cursor_position`, `text_length`, `is_auto_repeat`. (Index `session_id` for fast retrieval).

### Frontend Responsibilities (React + Monaco/CodeMirror)
The frontend must explicitly:
1. Provide registration and login screens.
2. Display programming tasks and a session timer.
3. Capture keystroke events and buffer them locally.
4. Send batched event data via JSON.
5. Prevent copy-paste to preserve typing authenticity.
6. **Strict Anti-Bias:** Explicitly disable browser autocomplete, spellcheck, text-prediction, and context menus to ensure all inputs are genuine keystrokes.

---

# Example Event Payload

The frontend must send batched keystrokes to the backend using this exact JSON structure:

{
  "session_id": "abc123",
  "events": [
    {
      "key": "f",
      "event_type": "keydown",
      "timestamp": 12345.6789,
      "cursor_position": 5,
      "text_length": 5,
      "is_auto_repeat": false
    },
    {
      "key": "f",
      "event_type": "keyup",
      "timestamp": 12400.1234,
      "cursor_position": 5,
      "text_length": 5,
      "is_auto_repeat": false
    }
  ]
}

---

# Development Workflow & Version Control

The codebase must be built iteratively. You must strictly adhere to the following workflow:
- **Target Shell:** Execute all terminal commands using PowerShell.
- **Atomic Commits:** After completing every single functional unit (e.g., after the schema is built, after the API is set up), automatically stage the changes and execute a `git commit` via PowerShell.
- **Commit Messages:** Use clear, conventional commit messages explaining exactly what was just built.
- **No Batching:** Do not attempt to build the entire full-stack application in one giant step before committing. Build and commit iteratively.

---

# Required Deliverables
1. PostgreSQL schema and database connection setup.
2. FastAPI backend with `/register`, `/login`, `/session/start`, `/session/end`, and `/keystrokes/batch` endpoints.
3. React frontend with the code editor, event buffering logic, and strict anti-bias measures.
4. Local setup instructions (`README.md`).