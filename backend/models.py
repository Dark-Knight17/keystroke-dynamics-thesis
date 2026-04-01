import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Boolean, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matric_hash = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
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

class KeystrokeEvent(Base):
    __tablename__ = "keystroke_events"
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.session_id"), nullable=False)
    key = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    timestamp = Column(Float, nullable=False)  # performance.now() high-res
    cursor_position = Column(Integer)
    text_length = Column(Integer)
    is_auto_repeat = Column(Boolean, default=False)

# Index session_id for fast retrieval
Index("ix_keystroke_events_session_id", KeystrokeEvent.session_id)
