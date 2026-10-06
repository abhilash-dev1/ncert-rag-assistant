import os
import re
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
PDF_FOLDER = os.getenv("PDF_FOLDER", r"C:\DOWNLOADS\NCERT-RAG-PROJECT-MAIN\BACKEND\PDFS")
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ✅ Qdrant Configuration
QDRANT_URL = os.getenv("https://2cd37365-8851-4778-b10c-62191878b96f.sa-east-1-0.aws.cloud.qdrant.io")
QDRANT_API_KEY = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6ZGE1OTlmMGQtMjg4YS00NjdlLWE2YzctMzY1MDNlY2ZhZTkyIn0.HwMEIl53d3tXMEl7txCbYSCWF3OfXckh0POHQNlkrEk")
COLLECTION_NAME = "ncert_search"

embedding_model = None
qdrant_client = None

def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return embedding_model

def get_qdrant_client():
    global qdrant_client
    if qdrant_client is None:
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise ValueError("❌ QDRANT_URL and QDRANT_API_KEY must be set in environment variables.")
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Create collection if it doesn't exist
        collections = qdrant_client.get_collections().collections
        if not any(c.name == COLLECTION_NAME for c in collections):
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            print(f"✅ Created Qdrant collection: {COLLECTION_NAME}")
    return qdrant_client

def clean_chunk_text(text):
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'Reprint\s*\d{4}-\d{2}', ' ', text)
    text = re.sub(r'\w+\.indd', ' ', text)
    text = re.sub(r'\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}:\d{2}', ' ', text)
    text = re.sub(r'\d{2}-\d{2}-\d{4}\s*\d{2}:\d{2}:\d{2}', ' ', text)
    text = re.sub(r'\b(?:ll|ii|ff|vv|oo|pp|rr|ss|tt)\b', ' ', text)
    text = re.sub(r'\b(?:Contents|Foreword|Preface|Rationalisation|Glossary|Overview)\b', ' ', text)
    text = re.sub(r'(Fill in the blanks|Choose the correct option|Match the following|State whether true or false)', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )

    all_chunks = []
    all_metadata = []

    for pdf_path in pdf_files:
        subject_folder = os.path.basename(os.path.dirname(pdf_path))
        book_name = subject_folder
        chapter_name = os.path.basename(pdf_path)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    if page_num < 10: continue # Skip foreword/preface
                        
                    text = page.extract_text()
                    if text and text.strip():
                        text = clean_chunk_text(text)
                        page_chunks = text_splitter.split_text(text)
                        for chunk in page_chunks:
                            if len(chunk) > 50:
                                all_chunks.append(chunk)
                                all_metadata.append({
                                    "book_id": book_name,
                                    "chapter_id": chapter_name,
                                    "page": page_num + 1
                                })
        except Exception as e:
            print(f"⚠️ Failed to read {pdf_path}: {e}")

    if not all_chunks:
        print("❌ No text extracted.")
        return

    model = get_embedding_model()
    print("🔄 Generating embeddings...")
    embeddings = model.encode(all_chunks, show_progress_bar=True)

    client = get_qdrant_client()
    
    # ✅ Clear old data in Qdrant
    try:
        client.delete_collection(collection_name=COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        print("🧹 Cleared old Qdrant collection.")
    except Exception as e:
        print(f"⚠️ Could not clear collection: {e}")

    # ✅ Upload to Qdrant in batches
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
        print(f"✅ Uploaded batch {i//batch_size + 1} ({end_idx - i} chunks)")

    print(f"✅ Indexed {len(all_chunks)} chunks to Qdrant Cloud.")

def search_similar(query, book_id=None, top_k=5):
    model = get_embedding_model()
    query_embedding = model.encode([query])[0]
    client = get_qdrant_client()
    
    # Build filter
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    query_filter = None
    if book_id:
        query_filter = Filter(
            must=[FieldCondition(key="book_id", match=MatchValue(value=book_id))]
        )

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding.tolist(),
        limit=top_k,
        query_filter=query_filter
    )

    if not results:
        return [], [], []

    valid_chunks = [hit.payload["text"] for hit in results]
    valid_metadata = [{"book_id": hit.payload["book_id"], "chapter_id": hit.payload["chapter_id"], "page": hit.payload["page"]} for hit in results]
    scores = [hit.score for hit in results]

    return valid_chunks, valid_metadata, scores