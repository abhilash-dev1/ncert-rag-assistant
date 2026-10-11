import os
import re
import json
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from rag_search import build_index, search_similar, get_qdrant_client
from database import get_db, init_db, User, ChatSession, ChatMessage, Note, BookAccess
from google import genai
import sqlite3
import html as html_escape

app = FastAPI(title="NCERT RAG (Gemini Tutor)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HF_USERNAME = "abhilash-pokuri123"
HF_DATASET = "ncert-pdfs"
HF_BASE_URL = f"https://huggingface.co/datasets/{HF_USERNAME}/{HF_DATASET}/resolve/main"
HF_TREE_URL = f"https://huggingface.co/api/datasets/{HF_USERNAME}/{HF_DATASET}/tree/main"

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
    user_id: Optional[int] = 1

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
    user_id: Optional[int] = 1

class ProgressCreate(BaseModel):
    book_id: str
    last_page: int
    user_id: Optional[int] = 1

# ✅ Reverse-text detector & fixer (for mirrored PDF pages)
def is_reversed(text):
    sample = ' ' + text.lower() + ' '
    rev_markers = [' eht ', ' dna ', ' fo ', ' ot ', ' ni ', ' si ', ' ta ', ' rof ']
    norm_markers = [' the ', ' and ', ' of ', ' to ', ' in ', ' is ', ' at ', ' for ']
    rev_count = sum(1 for m in rev_markers if m in sample)
    norm_count = sum(1 for m in norm_markers if m in sample)
    return rev_count >= 2 and rev_count > norm_count

def fix_reversed_chunks(chunks):
    fixed = []
    for c in chunks:
        if is_reversed(c):
            fixed.append(c[::-1])
            print(f"🔄 Reversed a chunk: {c[:40]}...")
        else:
            fixed.append(c)
    return fixed

# --- TEXTBOOKS & CHAPTERS ---
@app.get("/api/textbooks")
async def get_textbooks():
    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            response = await http_client.get(HF_TREE_URL)
            response.raise_for_status()
            items = response.json()

            textbooks = []
            for item in items:
                if item["type"] == "directory":
                    folder_name = item["path"]
                    chapters_url = f"{HF_TREE_URL}/{folder_name}"
                    ch_resp = await http_client.get(chapters_url)
                    if ch_resp.status_code == 200:
                        ch_items = ch_resp.json()
                        pdfs = [f["path"].split("/")[-1] for f in ch_items if f["type"] == "file" and f["path"].lower().endswith(".pdf")]
                        pdfs.sort(key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
                        if pdfs:
                            textbooks.append({"folder": folder_name, "chapters": pdfs})

            print(f"📚 Loaded {len(textbooks)} textbooks from Hugging Face")
            return {"textbooks": textbooks}
    except Exception as e:
        print(f"⚠️ Error fetching textbooks: {e}")
        return {"textbooks": []}

@app.get("/api/chapters/{folder_name}")
async def get_chapters(folder_name: str):
    try:
        chapters_url = f"{HF_TREE_URL}/{folder_name}"
        async with httpx.AsyncClient(timeout=60) as http_client:
            response = await http_client.get(chapters_url)
            response.raise_for_status()
            items = response.json()
        pdfs = [f["path"].split("/")[-1] for f in items if f["type"] == "file" and f["path"].lower().endswith(".pdf")]
        pdfs.sort(key=lambda x: int(''.join(filter(str.isdigit, x)) or 0))
        return {"chapters": pdfs}
    except Exception as e:
        print(f"⚠️ Error fetching chapters: {e}")
        return {"chapters": []}

@app.get("/api/pdf/{folder_name}/{chapter_name}")
async def serve_pdf(folder_name: str, chapter_name: str):
    pdf_url = f"{HF_BASE_URL}/{folder_name}/{chapter_name}"
    print(f"📄 Fetching PDF: {pdf_url}")
    try:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as http_client:
            response = await http_client.get(pdf_url)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="PDF not found")
            print(f"✅ Served PDF: {chapter_name} ({len(response.content)} bytes)")
            return Response(content=response.content, media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename={chapter_name}", "Access-Control-Allow-Origin": "*"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ Error serving PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch PDF")

# --- AUTH APIs ---
@app.post("/api/auth/google")
async def google_auth(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.google_id == user.google_id).first()
    if existing:
        print(f"👤 Existing user logged in: {user.email} (ID: {existing.id})")
        return {"message": "User already exists", "user_id": existing.id}
    new_user = User(email=user.email, name=user.name, google_id=user.google_id, profile_pic=user.profile_pic)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"✨ New user created: {user.email} (ID: {new_user.id})")
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
    print(f"\n📥 Received: {request.question} | User: {request.user_id} | Book: {request.book_id} | Chapter: {request.chapter_id}")

    is_summary_request = any(word in request.question.lower() for word in
        ["explain", "summary", "summarize", "what is this chapter", "about", "full concept",
         "teach me", "what concepts", "what are the", "what topics", "overview",
         "introduction", "describe", "why should i learn", "why learn", "what is", "how to"]
    )

    chunks = []
    metadata = []
    scores = []

    try:
        if is_summary_request and request.book_id and request.chapter_id:
            print("📖 Summary request detected. Fetching chapter chunks from Qdrant...")
            qclient = get_qdrant_client()
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            query_filter = Filter(must=[
                FieldCondition(key="book_id", match=MatchValue(value=request.book_id)),
                FieldCondition(key="chapter_id", match=MatchValue(value=request.chapter_id))
            ])
            results = qclient.scroll(collection_name="ncert_search", scroll_filter=query_filter, limit=2000)
            points = results[0]
            if points:
                chunks = [p.payload["text"] for p in points]
                metadata = [{"book_id": p.payload["book_id"], "chapter_id": p.payload["chapter_id"], "page": p.payload["page"]} for p in points]
                scores = [0.9] * len(chunks)
                print(f"📚 Loaded {len(chunks)} chunks from chapter")
            else:
                chunks, metadata, scores = search_similar(query=request.question, book_id=request.book_id, top_k=8)
        else:
            chunks, metadata, scores = search_similar(query=request.question, book_id=request.book_id, top_k=8)
            print(f"📚 RAG found {len(chunks)} chunks")
    except Exception as e:
        print(f"⚠️ Search Error: {e}")
        chunks, metadata, scores = [], [], []

    if chunks:
        chunks = fix_reversed_chunks(chunks)

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
        final_answer = "I searched the textbook, but I couldn't find a clear answer. Please try asking a more specific question about the chapter."
        source_list = []

    session = None
    if request.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()

    if not session:
        session = ChatSession(
            user_id=request.user_id or 1,
            book_id=request.book_id,
            chapter_id=request.chapter_id,
            title=request.question[:30] + '...'
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        print(f"✨ Created new session: {session.id} for user {session.user_id}")

    try:
        db.add(ChatMessage(chat_session_id=session.id, sender='user', text=request.question))
        db.add(ChatMessage(chat_session_id=session.id, sender='ai', text=final_answer, sources=json.dumps(source_list)))
        db.commit()
    except Exception as e:
        print(f"⚠️ DB Error: {e}")

    return SearchResponse(answer=final_answer, sources=source_list, chunks=chunks[:5], scores=scores[:5], session_id=session.id)

# --- NOTES APIs ---
@app.post("/api/notes")
async def create_note(note: NoteCreate, db: Session = Depends(get_db)):
    new_note = Note(
        user_id=note.user_id or 1,
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
    uid = progress.user_id or 1
    existing = db.query(BookAccess).filter(BookAccess.user_id == uid, BookAccess.book_id == progress.book_id).first()
    if existing:
        existing.last_page = progress.last_page
        existing.last_opened = datetime.utcnow()
    else:
        db.add(BookAccess(user_id=uid, book_id=progress.book_id, last_page=progress.last_page))
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
    rag_context = "\n\n---\n\n".join(chunks)

    if is_summary:
        prompt = f"""You are a friendly, expert NCERT tutor for Indian school students.

Student's Question: {question}

FULL CHAPTER CONTEXT (from the actual textbook):
{rag_context}

INSTRUCTIONS:
- Give a COMPREHENSIVE and DETAILED answer (at least 3-5 paragraphs or a structured explanation).
- Use ONLY information from the context above.
- Explain concepts clearly with examples from the text.
- Use simple language for a school student.
- Do NOT mention page numbers, "Contents", or metadata.
- Structure your answer with clear headings or bullet points if helpful.

Answer:"""
    else:
        prompt = f"""You are a friendly, expert NCERT tutor for Indian school students.

Student's Question: {question}

TEXTBOOK CONTEXT (Use ONLY this to answer):
{rag_context}

INSTRUCTIONS:
- Give a DETAILED and COMPREHENSIVE answer (at least 2-3 paragraphs).
- Explain your answer using evidence from the textbook context.
- Do NOT give one-line answers. Provide reasoning and examples.
- Use simple language for a school student.
- IGNORE page numbers, "Contents", "Foreword", "Preface".
- If the answer truly cannot be found, say "I could not find the specific answer in this chapter's text."

Answer:"""
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

# --- ADMIN DB VIEWER ---
@app.get("/admin/db", response_class=HTMLResponse)
async def admin_db_view():
    db_path = "/tmp/ncert_rag.db"
    if not os.path.exists(db_path):
        return HTMLResponse("""<body style='font-family:sans-serif;padding:40px;background:#0f172a;color:#e2e8f0'>
        <h1>⚠️ No database yet</h1>
        <p>Sign in to your app first, then refresh this page.</p>
        <p style='color:#64748b;font-size:14px'>Looking for: /tmp/ncert_rag.db</p>
        </body>""")

    tables = ["users", "chat_sessions", "chat_messages", "notes", "book_access"]
    html_parts = ["""<!DOCTYPE html>
    <html><head><title>NCERT RAG DB Viewer</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; margin: 0; }
        h1 { color: #f87171; margin-bottom: 8px; }
        .subtitle { color: #94a3b8; font-size: 14px; margin-bottom: 24px; }
        h2 { color: #60a5fa; margin-top: 32px; border-bottom: 2px solid #334155; padding-bottom: 8px; font-size: 18px; }
        table { border-collapse: collapse; width: 100%; margin-top: 12px; background: #1e293b; font-size: 13px; }
        th, td { border: 1px solid #334155; padding: 8px 12px; text-align: left; vertical-align: top; max-width: 400px; overflow-wrap: break-word; }
        th { background: #1e40af; color: white; font-weight: 600; position: sticky; top: 0; }
        tr:nth-child(even) { background: #0f172a; }
        tr:hover { background: #1e40af22; }
        .empty { color: #64748b; font-style: italic; padding: 12px; background: #1e293b; border-radius: 6px; }
        .count { color: #94a3b8; font-size: 13px; font-weight: normal; }
        .refresh { display: inline-block; background: #3b82f6; color: white; padding: 8px 16px; text-decoration: none; border-radius: 6px; margin-top: 12px; font-size: 14px; }
        .refresh:hover { background: #2563eb; }
    </style></head><body>
    <h1>📊 NCERT RAG Database Viewer</h1>
    <p class="subtitle">Live view of <code>/tmp/ncert_rag.db</code> on Railway · <a href="/admin/db" class="refresh">🔄 Refresh</a></p>
    """]

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for table in tables:
            try:
                rows = cursor.execute(f"SELECT * FROM {table}").fetchall()
                html_parts.append(f"<h2>{table} <span class='count'>({len(rows)} rows)</span></h2>")
                if not rows:
                    html_parts.append("<p class='empty'>No rows yet.</p>")
                    continue
                html_parts.append("<table><thead><tr>")
                for col in rows[0].keys():
                    html_parts.append(f"<th>{html_escape.escape(str(col))}</th>")
                html_parts.append("</tr></thead><tbody>")
                for row in rows:
                    html_parts.append("<tr>")
                    for val in row:
                        cell = html_escape.escape(str(val)) if val is not None else "<i style='color:#64748b'>NULL</i>"
                        html_parts.append(f"<td>{cell}</td>")
                    html_parts.append("</tr>")
                html_parts.append("</tbody></table>")
            except Exception as e:
                html_parts.append(f"<p class='empty'>Error reading {table}: {e}</p>")

        conn.close()
        html_parts.append("</body></html>")
        return HTMLResponse("".join(html_parts))
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {e}</h1>")