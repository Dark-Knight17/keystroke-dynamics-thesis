import uuid
import hashlib
import hmac
import jwt
import os
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel

import models, database

# Security setup
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI(title="Keystroke Dynamics Platform")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    event_type: str
    timestamp: float
    cursor_position: int
    text_length: int
    is_auto_repeat: bool

class KeystrokeBatch(BaseModel):
    session_id: str
    events: List[KeystrokeEventCreate]

class SessionStart(BaseModel):
    task_id: int
    device_type: str
    keyboard_layout: str
    os: str

# Create tables
models.Base.metadata.create_all(bind=database.engine)

# Helper functions
SECRET_PEPPER = "my-super-secret-research-key-2026"
JWT_SECRET = SECRET_PEPPER

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

# Endpoints
@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(database.get_db)):
    try:
        # Check if user already exists based on matric_hash (stable hash would be better, but sticking to salt for now)
        # To avoid brute-force scanning all users for every registration, we just try to create.
        # If there's a unique constraint on matric_hash, DB will throw.
        matric_hash = get_stable_hash(user_in.matric_number)
        password_hash = get_password_hash(user_in.password)
        
        db_user = models.User(matric_hash=matric_hash, password_hash=password_hash)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Create participant record by unpacking the Pydantic model
        # Exclude User-specific fields that are not in the Participant model
        participant_data = user_in.dict(exclude={'matric_number', 'password'})
        
        participant = models.Participant(
            user_id=db_user.user_id,
            **participant_data
        )
        db.add(participant)
        db.commit()
        
        return {"user_id": str(db_user.user_id), "message": "User registered successfully"}
    except Exception as e:
        db.rollback()
        print(f"Registration Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/login")
def login(user_in: UserLogin, db: Session = Depends(database.get_db)):
    # 1. Hash the incoming matric number using our new stable function
    search_matric_hash = get_stable_hash(user_in.matric_number)
    
    # 2. Ask the database to find the EXACT match (Lightning fast!)
    target_user = db.query(models.User).filter(models.User.matric_hash == search_matric_hash).first()
    
    # 3. If the user doesn't exist, OR if the randomly-salted password doesn't match, reject them.
    if not target_user or not verify_password(user_in.password, target_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
        
    # 4. Generate a secure JWT token (2 hours expiration)
    access_token_expires = timedelta(minutes=120)
    access_token = create_access_token(
        data={"sub": str(target_user.user_id)}, 
        expires_delta=access_token_expires
    )
    
    return {
        "user_id": str(target_user.user_id), 
        "access_token": access_token, 
        "token_type": "bearer"
    }

@app.post("/session/start")
def start_session(session_in: SessionStart, user_id: str, db: Session = Depends(database.get_db)):
    # Check if participant exists for this user_id
    participant = db.query(models.Participant).filter(models.Participant.user_id == user_id).first()
    if not participant:
        participant = models.Participant(
            user_id=user_id,
            device_type=session_in.device_type,
            keyboard_layout=session_in.keyboard_layout,
            os=session_in.os
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
    
    new_session = models.Session(
        participant_id=participant.participant_id,
        task_id=session_in.task_id
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {"session_id": str(new_session.session_id)}

@app.post("/session/end/{session_id}")
def end_session(session_id: str, db: Session = Depends(database.get_db)):
    db_session = db.query(models.Session).filter(models.Session.session_id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db_session.end_time = datetime.utcnow()
    # total_keystrokes will be calculated from KeystrokeEvent count
    count = db.query(models.KeystrokeEvent).filter(models.KeystrokeEvent.session_id == session_id).count()
    db_session.total_keystrokes = count
    db.commit()
    
    return {"message": "Session ended", "total_keystrokes": count}

@app.post("/keystrokes/batch")
def upload_keystrokes(batch: KeystrokeBatch, db: Session = Depends(database.get_db)):
    session_id = uuid.UUID(batch.session_id)
    events = []
    for event_in in batch.events:
        event = models.KeystrokeEvent(
            session_id=session_id,
            key=event_in.key,
            event_type=event_in.event_type,
            timestamp=event_in.timestamp,
            cursor_position=event_in.cursor_position,
            text_length=event_in.text_length,
            is_auto_repeat=event_in.is_auto_repeat
        )
        events.append(event)
    
    db.add_all(events)
    db.commit()
    
    return {"status": "success", "count": len(events)}

@app.get("/tasks")
def get_tasks(db: Session = Depends(database.get_db)):
    return db.query(models.ProgrammingTask).all()

@app.get("/participant/{user_id}")
def get_participant(user_id: str, db: Session = Depends(database.get_db)):
    participant = db.query(models.Participant).filter(models.Participant.user_id == user_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    return participant

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
