import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Boolean, Index, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matric_hash = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Participant(Base):
    __tablename__ = "participants"
    participant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    device_type = Column(String)
    keyboard_layout = Column(String)
    os = Column(String)
    physical_keyboard_type = Column(String, nullable=True)

class ProgrammingTask(Base):
    __tablename__ = "programming_tasks"
    task_id = Column(Integer, primary_key=True, index=True)
    task_title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    day = Column(Integer, default=1)
    difficulty_level = Column(String)
    expected_solution_length = Column(Integer)

class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.participant_id"), nullable=False)
    task_id = Column(Integer, ForeignKey("programming_tasks.task_id"), nullable=False)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True))
    total_keystrokes = Column(Integer, default=0)
    epoch_anchor = Column(BigInteger)
    final_editor_text = Column(Text, nullable=True)
    is_fragmented = Column(Boolean, default=False) # Flag for missing event sequences
    last_inference_ms = Column(Float, nullable=True) # Performance metric for FYP reporting

class KeystrokeEvent(Base):
    __tablename__ = "keystroke_events"
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.session_id"), nullable=False)
    key = Column(String, nullable=False)
    physical_code = Column(String, nullable=True) # e.code from browser
    event_type = Column(String, nullable=False)
    timestamp = Column(Float, nullable=False)  # performance.now() high-res
    cursor_position = Column(Integer)
    text_length = Column(Integer)
    is_auto_repeat = Column(Boolean, default=False)
    is_modifier = Column(Boolean, default=False)
    event_sequence = Column(Integer, nullable=False)
    server_received_at = Column(DateTime(timezone=True), server_default=func.now())
    batch_id = Column(String, nullable=False, index=True)  # For batch processing and ordering

# Index session_id for fast retrieval
Index("ix_keystroke_events_session_id", KeystrokeEvent.session_id)

# ── Authentication Schemas ──
from pydantic import BaseModel, ConfigDict
from typing import List

class KeystrokeEventPayload(BaseModel):
    """
    Represents a single keystroke event sent from the frontend.
    """
    physical_code: str
    timestamp: float
    event_type: str
    text_length: int
    event_sequence: int

    model_config = ConfigDict(from_attributes=True)

class AuthVerifyRequest(BaseModel):
    """
    Represents the full request body for the verification endpoint.
    """
    events: List[KeystrokeEventPayload]

    model_config = ConfigDict(from_attributes=True)
