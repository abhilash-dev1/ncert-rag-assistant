import os
import re
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ✅ Force load .env from exact folder
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from rag_search import build_index, search_similar, get_qdrant_client
from database import get_db, init_db, User, ChatSession, ChatMessage, Note, BookAccess
from google import genai

app = FastAPI(title="NCERT RAG (Gemini Tutor)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PDF_DIRECTORY = os.getenv("PDF_FOLDER", "./PDFS")
if os.path.exists(PDF_DIRECTORY):
    app.mount("/api/pdf", StaticFiles(directory=PDF_DIRECTORY), name="pdfs")
    print(f"✅ Mounted PDF directory: {PDF_DIRECTORY}")
else:
    print(f"⚠️ PDF directory not found at {PDF_DIRECTORY}. PDF viewer will not work, but Chat will.")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database initialized!")
    print("📚 Search index is ready!")

# --- REQUEST MODELS ---
class SearchRequest(BaseModel):
    question: str
    book_id: Optional[str] = None
    chapter_id: Optional[str] = None
    session_id: Optional[int] = None

class SearchResponse(BaseModel):
    answer: str
    sources: list[str]
    chunks: list[str] = []
    scores: list[float] = []
    session_id: Optional[int] = None

class UserCreate(BaseModel):
    email: str
    name: str
    google_id: str
    profile_pic: Optional[str] = None

class NoteCreate(BaseModel):
    book_id: str
    chapter_id: Optional[str] = None
    page_number: int
    content: str

class ProgressCreate(BaseModel):
    book_id: str
    last_page: int

# --- TEXTBOOKS & CHAPTERS ---
@app.get("/api/textbooks")
async def get_textbooks():
    textbooks = []
    if not os.path.exists(PDF_DIRECTORY):
        return {"textbooks": []}
    for folder_name in os.listdir(PDF_DIRECTORY):
        folder_path = os.path.join(PDF_DIRECTORY, folder_name)
        if os.path.isdir(folder_path):
            pdfs = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
            if len(pdfs) > 0:
                textbooks.append({
                    "folder": folder_name,
                    "chapters": sorted(pdfs, key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
                })
    return {"textbooks": textbooks}

@app.get("/api/chapters/{folder_name}")
async def get_chapters(folder_name: str):
    folder_path = os.path.join(PDF_DIRECTORY, folder_name)
    if not os.path.exists(folder_path):
        return {"chapters": []}
    pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
    pdf_files.sort(key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
    return {"chapters": pdf_files}

# --- AUTH APIs ---
@app.post("/api/auth/google")
async def google_auth(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.google_id == user.google_id).first()
    if existing:
        return {"message": "User already exists", "user_id": existing.id}
    new_user = User(email=user.email, name=user.name, google_id=user.google_id, profile_pic=user.profile_pic)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created", "user_id": new_user.id}

@app.get("/api/auth/me/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "email": user.email, "name": user.name, "profile_pic": user.profile_pic}

# --- CHAT APIs ---
@app.get("/api/chat/{session_id}")
async def get_chat_by_id(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id).order_by(ChatMessage.id).all()
    return {
        "session_id": session.id,
        "title": session.title,
        "messages": [{"id": m.id, "sender": m.sender, "text": m.text, "sources": m.sources} for m in messages]
    }

@app.get("/api/chat/history/{user_id}")
async def get_chat_history(user_id: int, book_id: str = None, chapter_id: str = None, db: Session = Depends(get_db)):
    query = db.query(ChatSession).filter(ChatSession.user_id == user_id)
    if book_id:
        query = query.filter(ChatSession.book_id == book_id)
    if chapter_id:
        query = query.filter(ChatSession.chapter_id == chapter_id)
    sessions = query.order_by(ChatSession.created_at.desc()).limit(50).all()

    history = []
    for session in sessions:
        messages = db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id).all()
        if len(messages) == 0:
            continue
        history.append({
            "session_id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "messages": [{"sender": m.sender, "text": m.text, "sources": m.sources} for m in messages]
        })
    return {"history": history}

@app.post("/chat", response_model=SearchResponse)
async def chat(request: SearchRequest, db: Session = Depends(get_db)):
    print(f"\n📥 Received: {request.question} | Book: {request.book_id} | Chapter: {request.chapter_id} | Session: {request.session_id}")

    is_summary_request = any(word in request.question.lower() for word in 
        ["explain", "summary", "summarize", "what is this chapter", "about", "full concept", "teach me"]
    )

    chunks = []
    metadata = []
    scores = []

    try:
        if is_summary_request and request.book_id and request.chapter_id:
            # ✅ SUMMARY MODE: Fetch ALL chunks for this specific chapter from Qdrant
            print("📖 Summary request detected. Fetching all chunks for this chapter...")
            qclient = get_qdrant_client()
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            query_filter = Filter(
                must=[
                    FieldCondition(key="book_id", match=MatchValue(value=request.book_id)),
                    FieldCondition(key="chapter_id", match=MatchValue(value=request.chapter_id))
                ]
            )
            
            # Use Qdrant's scroll method to get all matching points
            results = qclient.scroll(
                collection_name="ncert_search",
                scroll_filter=query_filter,
                limit=1000
            )
            points = results[0]
            
            if points:
                chunks = [p.payload["text"] for p in points]
                metadata = [{"book_id": p.payload["book_id"], "chapter_id": p.payload["chapter_id"], "page": p.payload["page"]} for p in points]
                scores = [0.9] * len(chunks)
                print(f"📚 Loaded {len(chunks)} chunks from chapter {request.chapter_id}")
            else:
                print("⚠️ No chunks found in summary mode. Falling back to standard search...")
                chunks, metadata, scores = search_similar(query=request.question, book_id=request.book_id, top_k=5)
        else:
            # ✅ NORMAL MODE: Vector Search
            chunks, metadata, scores = search_similar(query=request.question, book_id=request.book_id, top_k=5)
            print(f"📚 RAG found {len(chunks)} chunks")
    except Exception as e:
        print(f"⚠️ Search Error: {e}")
        chunks, metadata, scores = [], [], []

    final_answer = ""
    source_list = []

    if chunks:
        try:
            if is_summary_request and metadata:
                paired = sorted(zip(chunks, metadata), key=lambda x: x[1].get('page', 0))
                chunks = [p[0] for p in paired]
                metadata = [p[1] for p in paired]

            final_answer = clean_with_llm(chunks, request.question, is_summary_request)
            source_list = list(set([f"Book: {m.get('book_id', 'Unknown')}, Page: {m.get('page', '?')}" for m in metadata]))
        except Exception as e:
            print(f"⚠️ LLM Error: {e}")
            final_answer = ""

    if not final_answer or len(final_answer.strip()) < 10:
        final_answer = "I searched the textbook, but I couldn't find a clear answer to that specific question. Please try asking a more specific question about the chapter."
        print("❌ RAG failed. No web fallback used.")
        source_list = []

    session = None
    if request.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()

    if not session:
        session = ChatSession(
            user_id=1,
            book_id=request.book_id,
            chapter_id=request.chapter_id,
            title=request.question[:30] + '...'
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        print(f"✨ Created new session: {session.id}")

    try:
        db.add(ChatMessage(chat_session_id=session.id, sender='user', text=request.question))
        db.add(ChatMessage(chat_session_id=session.id, sender='ai', text=final_answer, sources=json.dumps(source_list)))
        db.commit()
        print(f"✅ Saved messages to session: {session.id}")
    except Exception as e:
        print(f"⚠️ DB Error: {e}")

    return SearchResponse(
        answer=final_answer, 
        sources=source_list, 
        chunks=chunks[:5], 
        scores=scores[:5],
        session_id=session.id
    )

# --- NOTES APIs ---
@app.post("/api/notes")
async def create_note(note: NoteCreate, db: Session = Depends(get_db)):
    new_note = Note(
        user_id=1,
        book_id=note.book_id,
        chapter_id=note.chapter_id,
        page_number=note.page_number,
        content=note.content
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return {"message": "Note created", "note_id": new_note.id}

@app.get("/api/notes/{book_id}/{user_id}")
async def get_notes(book_id: str, user_id: int, chapter_id: str = None, db: Session = Depends(get_db)):
    query = db.query(Note).filter(Note.book_id == book_id, Note.user_id == user_id)
    if chapter_id:
        query = query.filter(Note.chapter_id == chapter_id)
    notes = query.all()
    return {"notes": [{"id": n.id, "page": n.page_number, "content": n.content} for n in notes]}

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return {"message": "Note deleted"}

# --- PROGRESS APIs ---
@app.post("/api/progress")
async def save_progress(progress: ProgressCreate, db: Session = Depends(get_db)):
    existing = db.query(BookAccess).filter(BookAccess.user_id == 1, BookAccess.book_id == progress.book_id).first()
    if existing:
        existing.last_page = progress.last_page
        existing.last_opened = datetime.utcnow()
    else:
        db.add(BookAccess(user_id=1, book_id=progress.book_id, last_page=progress.last_page))
    db.commit()
    return {"message": "Progress saved"}

@app.get("/api/progress/{book_id}/{user_id}")
async def get_progress(book_id: str, user_id: int, db: Session = Depends(get_db)):
    progress = db.query(BookAccess).filter(BookAccess.book_id == book_id, BookAccess.user_id == user_id).first()
    if progress:
        return {"last_page": progress.last_page}
    return {"last_page": 1}

# --- CLEAN AI FUNCTION ---
def clean_with_llm(chunks, question, is_summary=False):
    rag_context = "\n\n".join(chunks)
    
    if is_summary:
        prompt = f"""
You are a friendly, expert NCERT tutor for Indian school students.
The student is asking for a summary or explanation of the current chapter.

Student's Question: {question}

FULL CHAPTER CONTEXT (This is the entire chapter text):
{rag_context}

IMPORTANT RULES:
- Provide a comprehensive, well-structured summary of the ENTIRE chapter based on the context above.
- Break down the main themes, topics, and concepts.
- Use simple, engaging language appropriate for a school student.
- Do NOT mention page numbers or metadata.
- Structure your answer with clear headings or bullet points.

Answer:
"""
    else:
        prompt = f"""
You are a friendly, expert NCERT tutor for Indian school students.

Student's Question: {question}

TEXTBOOK CONTEXT (Use ONLY this to answer):
{rag_context}

IMPORTANT RULES:
- Write a NEW, CLEAN, and SIMPLE answer in your own words.
- IGNORE page numbers, "Contents", "Foreword", "Preface", metadata.
- Use simple language for a student.
- If the answer truly cannot be found in the context, say "I could not find the specific answer in this chapter's text."

Answer:
"""
    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.5-pro", "gemini-2.0-flash"]
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response.text and len(response.text.strip()) > 10:
                print(f"✅ Model '{model_name}' worked!")
                return response.text
        except Exception as e:
            print(f"⚠️ Model '{model_name}' failed: {e}")
            continue
    return ""

@app.get("/")
async def root():
    return {"status": "running", "message": "NCERT RAG Gemini Tutor is online!"}