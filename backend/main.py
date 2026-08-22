import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from rag_search import build_index, search_similar
from database import get_db, init_db, User, ChatSession, ChatMessage, Note, BookAccess
from google import genai

# ✅ Load environment variables (API key)
load_dotenv()

app = FastAPI(title="NCERT RAG (Gemini Tutor)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PDF_DIRECTORY = r"C:\DOWNLOADS\NCERT-RAG-PROJECT-MAIN\BACKEND\PDFS"

app.mount("/api/pdf", StaticFiles(directory=PDF_DIRECTORY), name="pdfs")
app.mount("/api/cover", StaticFiles(directory=PDF_DIRECTORY), name="covers")

# ✅ Load Gemini API key from .env
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
    book_id: str = None

class SearchResponse(BaseModel):
    answer: str
    sources: list[str]
    chunks: list[str] = []
    scores: list[float] = []

class UserCreate(BaseModel):
    email: str
    name: str
    google_id: str
    profile_pic: str = None

class NoteCreate(BaseModel):
    book_id: str
    page_number: int
    content: str

class ProgressCreate(BaseModel):
    book_id: str
    last_page: int

# --- TEXTBOOKS & CHAPTERS ---
@app.get("/api/textbooks")
async def get_textbooks():
    textbooks = []
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
    
    new_user = User(
        email=user.email,
        name=user.name,
        google_id=user.google_id,
        profile_pic=user.profile_pic
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created", "user_id": new_user.id}

@app.get("/api/auth/me/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_pic": user.profile_pic
    }

# --- CHAT APIs ---
@app.post("/api/chat/new")
async def create_new_chat(user_id: int, book_id: str = None, db: Session = Depends(get_db)):
    new_session = ChatSession(
        user_id=user_id,
        book_id=book_id,
        title="New Chat"
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"session_id": new_session.id, "title": new_session.title}

@app.get("/api/chat/{session_id}")
async def get_chat_by_id(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id).all()
    return {
        "session_id": session.id,
        "title": session.title,
        "messages": [{"sender": m.sender, "text": m.text, "sources": m.sources} for m in messages]
    }

@app.get("/api/chat/history/{user_id}")
async def get_chat_history(user_id: int, db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()).limit(50).all()
    
    history = []
    for session in sessions:
        messages = db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id).all()
        history.append({
            "session_id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "messages": [{"sender": m.sender, "text": m.text, "sources": m.sources} for m in messages]
        })
    
    return {"history": history}

@app.post("/chat", response_model=SearchResponse)
async def chat(request: SearchRequest, db: Session = Depends(get_db)):
    chunks, metadata, scores = search_similar(
        query=request.question,
        book_id=request.book_id,
        top_k=5
    )
    
    if not chunks:
        return SearchResponse(
            answer="I couldn't find any information about this in the NCERT textbooks.",
            sources=[]
        )
    
    final_answer = clean_with_llm(chunks, request.question)
    
    source_list = list(set([f"Book: {m['book_id']}, Page: {m['page']}" for m in metadata]))
    
    # Save to database
    session = ChatSession(
        user_id=1,
        book_id=request.book_id,
        title=request.question[:30] + '...'
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    user_msg = ChatMessage(
        chat_session_id=session.id,
        sender='user',
        text=request.question
    )
    db.add(user_msg)
    
    ai_msg = ChatMessage(
        chat_session_id=session.id,
        sender='ai',
        text=final_answer,
        sources=str(source_list)
    )
    db.add(ai_msg)
    db.commit()

    return SearchResponse(
        answer=final_answer,
        sources=source_list,
        chunks=chunks,
        scores=scores
    )

# --- NOTES APIs ---
@app.post("/api/notes")
async def create_note(note: NoteCreate, db: Session = Depends(get_db)):
    new_note = Note(
        user_id=1,
        book_id=note.book_id,
        page_number=note.page_number,
        content=note.content
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return {"message": "Note created", "note_id": new_note.id}

@app.get("/api/notes/{book_id}/{user_id}")
async def get_notes(book_id: str, user_id: int, db: Session = Depends(get_db)):
    notes = db.query(Note).filter(Note.book_id == book_id, Note.user_id == user_id).all()
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
    existing = db.query(BookAccess).filter(
        BookAccess.user_id == 1,
        BookAccess.book_id == progress.book_id
    ).first()
    
    if existing:
        existing.last_page = progress.last_page
        existing.last_opened = datetime.utcnow()
    else:
        new_progress = BookAccess(
            user_id=1,
            book_id=progress.book_id,
            last_page=progress.last_page
        )
        db.add(new_progress)
    
    db.commit()
    return {"message": "Progress saved"}

@app.get("/api/progress/{book_id}/{user_id}")
async def get_progress(book_id: str, user_id: int, db: Session = Depends(get_db)):
    progress = db.query(BookAccess).filter(
        BookAccess.book_id == book_id,
        BookAccess.user_id == user_id
    ).first()
    if progress:
        return {"last_page": progress.last_page}
    return {"last_page": 1}

# --- CLEAN AI FUNCTION ---
def clean_with_llm(chunks, question):
    context = "\n\n".join(chunks)
    q_lower = question.lower()

    if any(word in q_lower for word in ["short", "quick", "sum", "brief", "simple", "bullet", "small"]):
        size_instruction = "Keep the answer very short. Maximum 2-3 sentences."
    elif any(word in q_lower for word in ["detail", "thorough", "deep", "elaborate", "full", "explain everything", "large", "long"]):
        size_instruction = "Provide a detailed, thorough answer. Maximum 300 words."
    else:
        size_instruction = "Provide a clear, focused answer within 150 words."

    if any(word in q_lower for word in ["list", "types", "causes", "factors", "reasons", "features", "advantages", "disadvantages"]):
        structure_instruction = "Answer using clear bullet points."
    elif any(word in q_lower for word in ["timeline", "history", "process", "evolution", "sequence", "steps", "how did"]):
        structure_instruction = "Answer in chronological order or step-by-step sequence."
    elif any(word in q_lower for word in ["what is", "define", "meaning", "describe", "explain", "tell me about"]):
        structure_instruction = "Start with a clear definition, then explain briefly."
    else:
        structure_instruction = "Write a simple, clear, well-structured paragraph."

    prompt = f"""
You are a friendly, expert NCERT Social Studies tutor for Indian school students.

Student's Question: {question}

TEXTBOOK CONTEXT (Use ONLY this to answer):
{context}

INSTRUCTIONS FOR SIZE: {size_instruction}
INSTRUCTIONS FOR STRUCTURE: {structure_instruction}

IMPORTANT RULES:
- **DO NOT copy or repeat the raw context text.**
- **WRITE a NEW, CLEAN, and SIMPLE answer** in your own words.
- **IGNORE all page numbers, random numbers, "Contents", "Foreword", "Preface", "Chapter", "Reprint 2026", "LEADERS OF THE", "SOVIET UNION" etc.**
- If the context is confusing or doesn't make sense, say: "I found some information, but it's a bit unclear. Here's what I understand..."
- Use simple language that a 12th-grade student can understand.
- Keep your answer short and to the point.

Now, write the final answer for the student:
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"⚠️ Gemini Error: {e}")
        return " ".join(chunks)

@app.get("/")
async def root():
    return {"status": "running", "message": "NCERT RAG Gemini Tutor is online!"}