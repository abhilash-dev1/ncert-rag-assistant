import os
import re
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb

# --- CONFIG ---
PDF_FOLDER = r"C:\DOWNLOADS\NCERT-RAG-PROJECT-MAIN\BACKEND\PDFS"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

embedding_model = None
vector_collection = None

def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return embedding_model

def get_vector_collection():
    global vector_collection
    if vector_collection is not None:
        return vector_collection
    client = chromadb.PersistentClient(path="chroma_db")
    collection = client.get_or_create_collection(name="ncert_search")
    vector_collection = collection
    return collection

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
                    # ✅ SKIP THE FIRST 10 PAGES (Foreword, Preface, Copyright)
                    if page_num < 10:
                        continue
                        
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

    collection = get_vector_collection()
    ids = [f"{m['book_id']}_{m['chapter_id']}_p{m['page']}_c{i}" for i, m in enumerate(all_metadata)]
    
    try:
        collection.delete(where={"book_id": {"$ne": "dummy"}})
    except:
        pass

    batch_size = 5000
    for i in range(0, len(all_chunks), batch_size):
        end_idx = min(i + batch_size, len(all_chunks))
        collection.add(
            documents=all_chunks[i:end_idx],
            embeddings=embeddings[i:end_idx].tolist(),
            metadatas=all_metadata[i:end_idx],
            ids=ids[i:end_idx]
        )
        print(f"✅ Added batch {i//batch_size + 1} ({end_idx - i} chunks)")

    print(f"✅ Indexed {len(all_chunks)} chunks.")

def search_similar(query, book_id=None, top_k=5):
    model = get_embedding_model()
    query_embedding = model.encode([query])[0]
    collection = get_vector_collection()
    filter_dict = {"book_id": book_id} if book_id else None

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k,
        where=filter_dict
    )

    if not results["documents"][0]:
        return [], [], []

    cleaned_chunks = [clean_chunk_text(chunk) for chunk in results["documents"][0]]
    
    valid_chunks = []
    valid_metadata = []
    for chunk, meta in zip(cleaned_chunks, results["metadatas"][0]):
        if len(chunk) > 30:
            valid_chunks.append(chunk)
            valid_metadata.append(meta)

    scores = [0.9, 0.8, 0.7, 0.6, 0.5][:len(valid_chunks)]
    return valid_chunks, valid_metadata, scores