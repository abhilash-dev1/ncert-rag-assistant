from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# --- SQLITE DATABASE (EXACT PATH) ---
DATABASE_URL = "sqlite:///C:/Downloads/ncert-rag-project-main/backend/ncert_rag.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELS ---

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    google_id = Column(String, unique=True, index=True)
    profile_pic = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    chats = relationship("ChatSession", back_populates="user")
    notes = relationship("Note", back_populates="user")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    book_id = Column(String, nullable=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="chats")
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    sender = Column(String)
    text = Column(Text)
    sources = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="messages")


class Note(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    book_id = Column(String)
    page_number = Column(Integer, nullable=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notes")


class BookAccess(Base):
    __tablename__ = "book_access"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    book_id = Column(String)
    last_page = Column(Integer, default=1)
    last_opened = Column(DateTime, default=datetime.utcnow)

# --- INIT DATABASE ---
def init_db():
    Base.metadata.create_all(bind=engine)

# --- GET DATABASE SESSION ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()