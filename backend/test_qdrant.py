import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))

# 1. How many points are in the collection?
info = client.get_collection("ncert_search")
print(f"✅ Points count: {info.points_count}")

# 2. What does the stored data look like?
points, _ = client.scroll(collection_name="ncert_search", limit=3)
for p in points:
    print(f"   Sample: book_id='{p.payload.get('book_id')}' | chapter_id='{p.payload.get('chapter_id')}'")

# 3. Filter test — does the book_id/chapter_id combo match?
f = Filter(must=[
    FieldCondition(key="book_id", match=MatchValue(value="contemporary india (class 10)")),
    FieldCondition(key="chapter_id", match=MatchValue(value="chapter_2.pdf"))
])
r = client.scroll(collection_name="ncert_search", scroll_filter=f, limit=5)
print(f"✅ Filter for 'contemporary india (class 10)' + 'chapter_2.pdf': {len(r[0])} points found")