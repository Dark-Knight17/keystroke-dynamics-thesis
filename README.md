# AI-Based Keystroke Dynamics Data Collection Platform

This platform is designed to collect high-resolution keystroke dynamics data from programming tasks for research into continuous user authentication.

## Project Structure

- `backend/`: FastAPI application with PostgreSQL database.
- `frontend/`: React application using Monaco Editor for code input and keystroke logging.

## Features

- **High-Resolution Timing:** Sub-millisecond accuracy using `performance.now()`.
- **Anonymized Data:** Matriculation numbers and passwords are salted and hashed.
- **Batched Uploads:** Keystrokes are buffered locally and uploaded every 2 seconds or 50 events.
- **Anti-Bias Measures:** Disabled autocomplete, spellcheck, and copy-paste.

## Prerequisites

- Python 3.9+
- Node.js 16+
- PostgreSQL database

## Getting Started

### Backend Setup

1. Navigate to the `backend` directory:
   ```powershell
   cd backend
   ```
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Set up environment variables (create a `.env` file):
   ```env
   DATABASE_URL=postgresql://user:password@localhost/keystroke_db
   ```
5. Run the server:
   ```powershell
   uvicorn main:app --reload
   ```

### Frontend Setup

1. Navigate to the `frontend` directory:
   ```powershell
   cd frontend
   ```
2. Install dependencies:
   ```powershell
   npm install
   ```
3. Run the development server:
   ```powershell
   npm run dev
   ```

## Data Schema

The system uses a normalized relational schema stored in PostgreSQL:
- `users`: Participant credentials (hashed).
- `participants`: Anonymous device/OS metadata.
- `programming_tasks`: Coding exercises.
- `sessions`: Individual collection sessions.
- `keystroke_events`: Raw timing data for each key event.
