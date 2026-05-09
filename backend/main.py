import uuid
import hashlib
import hmac
import jwt
import os
from dotenv import load_dotenv
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import csv
import io

import models, database

load_dotenv()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Keystroke Dynamics Platform")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security setup
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# Pydantic Schemas
class UserCreate(BaseModel):
    matric_number: str
    password: str
    physical_keyboard_type: str
    keyboard_layout: Optional[str] = None
    device_type: Optional[str] = None
    os: Optional[str] = None
   

class UserLogin(BaseModel):
    matric_number: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class KeystrokeEventCreate(BaseModel):
    key: str
    physical_code: Optional[str] = None
    event_type: str
    timestamp: float
    cursor_position: int
    text_length: int
    is_auto_repeat: bool
    is_modifier: bool = False
    event_sequence: int

class SyncInfo(BaseModel):
    perf_now: float
    date_now: float

class KeystrokeBatch(BaseModel):
    session_id: str
    batch_id: str
    events: List[KeystrokeEventCreate]
    sync: Optional[SyncInfo] = None

class SessionStart(BaseModel):
    task_id: int
    device_type: str
    keyboard_layout: str
    os: str

class SessionComplete(BaseModel):
    final_editor_text: str

# Create tables
models.Base.metadata.create_all(bind=database.engine)

# Helper functions
SECRET_PEPPER = os.getenv("SECRET_PEPPER")
JWT_SECRET = os.getenv("JWT_SECRET")

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def get_stable_hash(identifier: str) -> str:
    """Creates a deterministic hash for database lookups."""
    return hmac.new(
        SECRET_PEPPER.encode('utf-8'),
        identifier.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def get_password_hash(password: str):
    # Pre-hash with SHA-256 to handle long inputs (bcrypt limit is 72 bytes)
    pre_hash = hashlib.sha256(password.encode()).hexdigest()
    # Explicitly truncate just in case pwd_context still complains
    return pwd_context.hash(pre_hash[:72])

def verify_password(plain_password: str, hashed_password: str):
    # Pre-hash with SHA-256 for verification
    pre_hash = hashlib.sha256(plain_password.encode()).hexdigest()
    return pwd_context.verify(pre_hash[:72], hashed_password)

def get_current_user(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Endpoints
@app.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, user_in: UserCreate, db: Session = Depends(database.get_db)):
    try:
        # Check if user already exists based on matric_hash
        matric_hash = get_stable_hash(user_in.matric_number)
        password_hash = get_password_hash(user_in.password)
        
        db_user = models.User(matric_hash=matric_hash, password_hash=password_hash)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        participant_data = user_in.dict(exclude={'matric_number', 'password'})
        
        participant = models.Participant(
            user_id=db_user.user_id,
            **participant_data
        )
        db.add(participant)
        db.commit()
        
        return {"user_id": str(db_user.user_id), "message": "User registered successfully"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this matriculation number already exists. Please log in."
        )
    except Exception as e:
        db.rollback()
        print(f"Registration Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/login")
@limiter.limit("10/minute")
def login(request: Request, user_in: UserLogin, response: Response, db: Session = Depends(database.get_db)):
    search_matric_hash = get_stable_hash(user_in.matric_number)
    target_user = db.query(models.User).filter(models.User.matric_hash == search_matric_hash).first()
    
    if not target_user or not verify_password(user_in.password, target_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(target_user.user_id)}, 
        expires_delta=access_token_expires
    )
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Changed from True to support non-HTTPS research environments
        samesite="lax",
        max_age=120 * 60
    )
    
    return {
        "user_id": str(target_user.user_id)
    }

@app.post("/session/start")
def start_session(
    session_in: SessionStart, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if participant exists for this user_id
    participant = db.query(models.Participant).filter(models.Participant.user_id == current_user.user_id).first()
    if not participant:
        participant = models.Participant(
            user_id=current_user.user_id,
            device_type=session_in.device_type,
            keyboard_layout=session_in.keyboard_layout,
            os=session_in.os
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
    
    # 1. Day-Locking Logic
    requested_task = db.query(models.ProgrammingTask).filter(models.ProgrammingTask.task_id == session_in.task_id).first()
    if not requested_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if requested_task.day > 1:
        # Check if all tasks from previous days are completed
        previous_tasks = db.query(models.ProgrammingTask).filter(models.ProgrammingTask.day < requested_task.day).all()
        for task in previous_tasks:
            completed = db.query(models.Session).filter(
                models.Session.participant_id == participant.participant_id,
                models.Session.task_id == task.task_id,
                models.Session.end_time != None
            ).first()
            if not completed:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Study Progression Locked: You must complete all Day {task.day} tasks before starting Day {requested_task.day}."
                )

    # Check for active, incomplete session for the requested task
    active_session = db.query(models.Session).filter(
        models.Session.participant_id == participant.participant_id,
        models.Session.task_id == session_in.task_id,
        models.Session.end_time == None
    ).first()
    
    if active_session:
        # Reuse active session instead of erroring out to be more robust
        return {"session_id": str(active_session.session_id)}

    new_session = models.Session(
        participant_id=participant.participant_id,
        task_id=session_in.task_id
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {"session_id": str(new_session.session_id)}

@app.post("/session/complete/{session_id}")
def complete_session(
    session_id: str,
    session_complete: SessionComplete,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Verify session belongs to user
    session_uuid = uuid.UUID(session_id)
    db_session = db.query(models.Session).join(models.Participant).filter(
        models.Session.session_id == session_uuid,
        models.Participant.user_id == current_user.user_id
    ).first()
    
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
    
    db_session.end_time = datetime.now(timezone.utc)
    db_session.final_editor_text = session_complete.final_editor_text
    
    # total_keystrokes will be calculated from KeystrokeEvent count
    count = db.query(models.KeystrokeEvent).filter(models.KeystrokeEvent.session_id == session_uuid).count()
    db_session.total_keystrokes = count
    db.commit()
    
    return {"message": "Session completed", "total_keystrokes": count}

@app.post("/session/end/{session_id}")
def end_session(
    session_id: str, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Backward compatibility
    return complete_session(session_id, SessionComplete(final_editor_text=""), db, current_user)

@app.post("/keystrokes/batch")
@limiter.limit("60/minute")
def upload_keystrokes(
    request: Request,
    batch: KeystrokeBatch, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Enforce strict maximum payload size
    if len(batch.events) > 200:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum allowed (200 events).")

    # Verify session belongs to user
    session_id = uuid.UUID(batch.session_id)
    db_session = db.query(models.Session).join(models.Participant).filter(
        models.Session.session_id == session_id,
        models.Participant.user_id == current_user.user_id
    ).first()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")

    # Update epoch_anchor if sync is provided
    if batch.sync:
        db_session.epoch_anchor = int(batch.sync.date_now)

    # Check for idempotency
    existing_batch = db.query(models.KeystrokeEvent).filter(
        models.KeystrokeEvent.batch_id == batch.batch_id
    ).first()
    if existing_batch:
        return {"status": "skipped", "message": "Batch already processed", "count": 0}

    events = []
    received_at = datetime.now(timezone.utc)
    for event_in in batch.events:
        event = models.KeystrokeEvent(
            session_id=session_id,
            key=event_in.key,
            physical_code=event_in.physical_code,
            event_type=event_in.event_type,
            timestamp=event_in.timestamp,
            cursor_position=event_in.cursor_position,
            text_length=event_in.text_length,
            is_auto_repeat=event_in.is_auto_repeat,
            is_modifier=event_in.is_modifier,
            event_sequence=event_in.event_sequence,
            batch_id=batch.batch_id,
            server_received_at=received_at
        )
        events.append(event)
    
    db.add_all(events)
    db.commit()
    
    return {"status": "success", "count": len(events)}

@app.get("/session/{session_id}/signature")
def get_session_signature(
    session_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Verify session belongs to user
    session_uuid = uuid.UUID(session_id)
    db_session = db.query(models.Session).join(models.Participant).filter(
        models.Session.session_id == session_uuid,
        models.Participant.user_id == current_user.user_id
    ).first()

    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")

    # Generate HMAC-SHA256 signature of the session_id
    signature = hmac.new(
        JWT_SECRET.encode('utf-8'),
        session_id.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return {"signature": signature}

@app.post("/keystrokes/beacon")
def upload_keystrokes_beacon(
    batch: KeystrokeBatch, 
    signature: str,
    db: Session = Depends(database.get_db)
):
    """Special endpoint for navigator.sendBeacon with HMAC signature validation."""
    # Validate signature
    expected_signature = hmac.new(
        JWT_SECRET.encode('utf-8'),
        batch.session_id.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=403, detail="Invalid beacon signature")

    session_id = uuid.UUID(batch.session_id)

    # Fetch session to update epoch_anchor if sync is provided
    db_session = db.query(models.Session).filter(models.Session.session_id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if batch.sync:
        db_session.epoch_anchor = int(batch.sync.date_now)
    
    existing_batch = db.query(models.KeystrokeEvent).filter(
        models.KeystrokeEvent.batch_id == batch.batch_id
    ).first()
    if existing_batch:
        return {"status": "skipped"}

    events = []
    received_at = datetime.now(timezone.utc)
    for event_in in batch.events:
        event = models.KeystrokeEvent(
            session_id=session_id,
            key=event_in.key,
            physical_code=event_in.physical_code,
            event_type=event_in.event_type,
            timestamp=event_in.timestamp,
            cursor_position=event_in.cursor_position,
            text_length=event_in.text_length,
            is_auto_repeat=event_in.is_auto_repeat,
            is_modifier=event_in.is_modifier,
            event_sequence=event_in.event_sequence,
            batch_id=batch.batch_id,
            server_received_at=received_at
        )
        events.append(event)
    
    db.add_all(events)
    db.commit()
    return {"status": "success"}

@app.get("/tasks")
def get_tasks(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    participant = db.query(models.Participant).filter(models.Participant.user_id == current_user.user_id).first()
    tasks = db.query(models.ProgrammingTask).all()
    
    if not participant:
        return [
            {
                **task.__dict__,
                "is_completed": False
            } for task in tasks if not task.__dict__.pop('_sa_instance_state', None)
        ]
        
    completed_task_ids = db.query(models.Session.task_id).filter(
        models.Session.participant_id == participant.participant_id,
        models.Session.end_time != None
    ).all()
    completed_task_ids = [tid[0] for tid in completed_task_ids]

    task_list = []
    for task in tasks:
        task_data = {c.name: getattr(task, c.name) for c in task.__table__.columns}
        task_data["is_completed"] = task.task_id in completed_task_ids
        task_list.append(task_data)
        
    return task_list

@app.get("/participant/{user_id}")
def get_participant(
    user_id: str, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if str(current_user.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to participant data")

    participant = db.query(models.Participant).filter(models.Participant.user_id == user_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    return participant

@app.get("/export/sessions")
def export_sessions(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "participant_id", "session_id", "task_id", "event_sequence", 
            "key", "physical_code", "event_type", "timestamp", "server_received_at", 
            "cursor_position", "text_length", "is_auto_repeat", "is_modifier"
        ])
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        # Batch query for efficiency
        query = db.query(
            models.Participant.participant_id,
            models.KeystrokeEvent.session_id,
            models.Session.task_id,
            models.KeystrokeEvent.event_sequence,
            models.KeystrokeEvent.key,
            models.KeystrokeEvent.physical_code,
            models.KeystrokeEvent.event_type,
            models.KeystrokeEvent.timestamp,
            models.KeystrokeEvent.server_received_at,
            models.KeystrokeEvent.cursor_position,
            models.KeystrokeEvent.text_length,
            models.KeystrokeEvent.is_auto_repeat,
            models.KeystrokeEvent.is_modifier
        ).join(
            models.Session, models.KeystrokeEvent.session_id == models.Session.session_id
        ).join(
            models.Participant, models.Session.participant_id == models.Participant.participant_id
        ).order_by(
            models.KeystrokeEvent.session_id, models.KeystrokeEvent.event_sequence
        )

        for row in query.all():
            writer.writerow(row)
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sessions_export.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
