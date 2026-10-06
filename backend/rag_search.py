import os
import re
import pdfplumber
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

PDF_FOLDER = os.getenv("PDF_FOLDER", r"C:\DOWNLOADS\NCERT-RAG-PROJECT-MAIN\BACKEND\PDFS")
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "ncert_search"

embedding_model = None
qdrant_client = None

def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
    return embedding_model

def ensure_indexes(client):
    try:
        client.create_payload_index(collection_name=COLLECTION_NAME, field_name="book_id", field_schema=PayloadSchemaType.KEYWORD)
        client.create_payload_index(collection_name=COLLECTION_NAME, field_name="chapter_id", field_schema=PayloadSchemaType.KEYWORD)
    except Exception:
        pass

def get_qdrant_client():
    global qdrant_client
    if qdrant_client is None:
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        if not url or not api_key:
            raise ValueError("❌ Missing Qdrant env vars.")
        if not url.endswith(":6333") and ":" not in url.split("//")[-1]:
            url = url.rstrip("/") + ":6333"
        qdrant_client = QdrantClient(url=url, api_key=api_key)
        collections = qdrant_client.get_collections().collections
        if not any(c.name == COLLECTION_NAME for c in collections):
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
        ensure_indexes(qdrant_client)
    return qdrant_client

def clean_chunk_text(text):
    # ✅ Remove repeated character garbage (CCCCooo -> C)
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    # ✅ Remove isolated single letters separated by spaces (e.g., "N M F T I S D L R")
    text = re.sub(r'\b(?:[A-Z]\s+){5,}[A-Z]?\b', ' ', text)
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'Reprint\s*\d{4}-\d{2}', ' ', text)
    text = re.sub(r'\w+\.indd', ' ', text)
    text = re.sub(r'\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2}', ' ', text)
    text = re.sub(r'\d{2}-\d{2}-\d{4}\s*\d{2}:\d{2}:\d{2}', ' ', text)
    text = re.sub(r'\b(?:ll|ii|ff|vv|oo|pp|rr|ss|tt)\b', ' ', text)
    text = re.sub(r'\b(?:Contents|Foreword|Preface|Rationalisation|Glossary|Overview|Index)\b', ' ', text)
    text = re.sub(r'(Fill in the blanks|Choose the correct option|Match the following|State whether true or false)', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_valid_chunk(chunk):
    """✅ Filter out garbage chunks"""
    if len(chunk) < 100:
        return False
    # Reject if too many single-letter tokens (OCR garbage)
    words = chunk.split()
    if not words:
        return False
    single_letter_ratio = sum(1 for w in words if len(w) == 1) / len(words)
    if single_letter_ratio > 0.4:
        return False
    # Reject if it's mostly the table of contents
    if chunk.lower().startswith("contents"):
        return False
    return True

def build_index(book_id=None):
    pdf_files = []
    if not os.path.exists(PDF_FOLDER):
        print(f"❌ Folder not found: {PDF_FOLDER}")
        return

    if book_id:
        for root, dirs, files in os.walk(PDF_FOLDER):
            for file in files:
                if file.lower().endswith(".pdf") and book_id.lower() in root.lower():
                    pdf_files.append(os.path.join(root, file))
    else:
        for root, dirs, files in os.walk(PDF_FOLDER):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))

    print(f"📂 Found {len(pdf_files)} PDF files.")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    all_chunks = []
    all_metadata = []

    for pdf_path in pdf_files:
        book_name = os.path.basename(os.path.dirname(pdf_path))
        chapter_name = os.path.basename(pdf_path)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    if page_num < 10: continue
                    text = page.extract_text()
                    if text and text.strip():
                        text = clean_chunk_text(text)
                        for chunk in text_splitter.split_text(text):
                            if is_valid_chunk(chunk):
                                all_chunks.append(chunk)
                                all_metadata.append({
                                    "book_id": book_name,
                                    "chapter_id": chapter_name,
                                    "page": page_num + 1
                                })
        except Exception as e:
            print(f"⚠️ Failed to read {pdf_path}: {e}")

    if not all_chunks:
        print("❌ No valid text extracted.")
        return

    model = get_embedding_model()
    print(f"🔄 Generating embeddings for {len(all_chunks)} chunks...")
    embeddings = list(model.embed(all_chunks))

    client = get_qdrant_client()
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        ensure_indexes(client)
    except Exception as e:
        print(f"⚠️ {e}")

    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        end_idx = min(i + batch_size, len(all_chunks))
        points = [
            PointStruct(
                id=i + j,
                vector=embeddings[i + j].tolist(),
                payload={
                    "text": all_chunks[i + j],
                    "book_id": all_metadata[i + j]["book_id"],
                    "chapter_id": all_metadata[i + j]["chapter_id"],
                    "page": all_metadata[i + j]["page"]
                }
            )
            for j in range(end_idx - i)
        ]
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        print(f"✅ Batch {i//batch_size + 1} uploaded ({end_idx - i} chunks)")

    print(f"✅ Indexed {len(all_chunks)} valid chunks.")

def search_similar(query, book_id=None, top_k=8):
    model = get_embedding_model()
    query_embedding = list(model.embed([query]))[0]
    client = get_qdrant_client()

    from qdrant_client.models import Filter, FieldCondition, MatchValue
    query_filter = Filter(
        must=[FieldCondition(key="book_id", match=MatchValue(value=book_id))]
    ) if book_id else None

    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding.tolist(),
            limit=top_k,
            query_filter=query_filter
        )
        points = results.points
    except AttributeError:
        points = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding.tolist(),
            limit=top_k,
            query_filter=query_filter
        )

    if not points:
        return [], [], []

    valid_chunks = [hit.payload["text"] for hit in points if is_valid_chunk(hit.payload["text"])]
    valid_metadata = [{"book_id": hit.payload["book_id"], "chapter_id": hit.payload["chapter_id"], "page": hit.payload["page"]} for hit in points if is_valid_chunk(hit.payload["text"])]
    scores = [hit.score for hit in points if is_valid_chunk(hit.payload["text"])]

    return valid_chunks, valid_metadata, scores