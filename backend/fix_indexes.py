import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))

# ✅ Create keyword indexes for filtering
client.create_payload_index(
    collection_name="ncert_search",
    field_name="book_id",
    field_schema=PayloadSchemaType.KEYWORD,
)
print("✅ Created index on 'book_id'")

client.create_payload_index(
    collection_name="ncert_search",
    field_name="chapter_id",
    field_schema=PayloadSchemaType.KEYWORD,
)
print("✅ Created index on 'chapter_id'")

# Verify
info = client.get_collection("ncert_search")
print(f"\n✅ Collection now has {info.points_count} points")
print(f"✅ Payload schema: {info.payload_schema}")