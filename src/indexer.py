import hashlib
import re
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

CURRICULUM_DIR = Path("./curriculum")
QDRANT_PATH = "./.qdrant_db"
COLLECTION_NAME = "daml_curriculum"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def chunk_markdown(file_path: Path) -> list[dict]:
    """Splits Markdown files into semantic chunks based on H2 headers."""
    content = file_path.read_text(encoding="utf-8")
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        cleaned = section.strip()
        if cleaned:
            chunk_id = hashlib.sha256(f"{file_path.name}:{cleaned}".encode()).hexdigest()[:32]
            chunks.append({
                "id": int(chunk_id[:15], 16),
                "source": file_path.name,
                "text": cleaned
            })
    return chunks


def build_index() -> None:
    if not CURRICULUM_DIR.exists():
        raise FileNotFoundError(f"Curriculum directory {CURRICULUM_DIR} does not exist.")

    model = SentenceTransformer(MODEL_NAME)
    vector_size = model.get_sentence_embedding_dimension()

    client = QdrantClient(path=QDRANT_PATH)
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    points = []
    for md_file in sorted(CURRICULUM_DIR.glob("*.md")):
        for chunk in chunk_markdown(md_file):
            vector = model.encode(chunk["text"], normalize_embeddings=True).tolist()
            points.append(
                PointStruct(
                    id=chunk["id"],
                    vector=vector,
                    payload={"source": chunk["source"], "text": chunk["text"]},
                )
            )

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        print(f"Successfully indexed {len(points)} curriculum chunks into Qdrant.")
    else:
        print("No Markdown content found to index.")


if __name__ == "__main__":
    build_index()
