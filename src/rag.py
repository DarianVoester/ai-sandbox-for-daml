"""RAG-Kern: Chunking, Embeddings und Qdrant mit EINEM gemeinsamen lokalen Client pro Prozess."""
import hashlib
import re
import threading
from pathlib import Path

import settings

_lock = threading.RLock()
_client = None
_client_path = None
_embedder = None


def get_client():
    """Gibt den gemeinsamen QdrantClient zurück (lokaler Modus erlaubt nur einen Prozess)."""
    global _client, _client_path
    with _lock:
        path = settings.QDRANT_PATH
        if _client is None or _client_path != path:
            close_client()
            from qdrant_client import QdrantClient

            try:
                _client = QdrantClient(path=path)
            except RuntimeError as e:
                raise RuntimeError(
                    f"Qdrant database is locked by another process ({e}). "
                    "Stop other Streamlit instances or src/indexer.py and reload."
                ) from e
            _client_path = path
        return _client


def close_client() -> None:
    global _client, _client_path
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
        _client = None
        _client_path = None


def get_embedder():
    """Lädt das Embedding-Modell erst bei Bedarf (schnellerer Seitenaufbau)."""
    global _embedder
    with _lock:
        if _embedder is None:
            from sentence_transformers import SentenceTransformer

            _embedder = SentenceTransformer(settings.MODEL_NAME)
        return _embedder


def chunk_markdown(file_path: Path) -> list[dict]:
    """Teilt Markdown-Dateien anhand von H2-Überschriften in Chunks."""
    content = file_path.read_text(encoding="utf-8")
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        cleaned = section.strip()
        if cleaned:
            chunk_id = hashlib.sha256(f"{file_path.name}:{cleaned}".encode()).hexdigest()[:32]
            chunks.append({"id": int(chunk_id[:15], 16), "source": file_path.name, "text": cleaned})
    return chunks


def index_count() -> int:
    client = get_client()
    if not client.collection_exists(settings.COLLECTION_NAME):
        return 0
    return client.count(collection_name=settings.COLLECTION_NAME, exact=True).count


def build_index(curriculum_dir: Path | None = None) -> int:
    """Baut die Collection neu auf und gibt die Anzahl der Chunks zurück."""
    from qdrant_client.models import Distance, PointStruct, VectorParams

    curriculum_dir = curriculum_dir or settings.CURRICULUM_DIR
    if not curriculum_dir.exists():
        raise FileNotFoundError(f"Curriculum directory {curriculum_dir} does not exist.")

    chunks = [c for md in sorted(curriculum_dir.glob("*.md")) for c in chunk_markdown(md)]

    with _lock:
        client = get_client()
        if client.collection_exists(settings.COLLECTION_NAME):
            client.delete_collection(settings.COLLECTION_NAME)
        embedder = get_embedder()
        client.create_collection(
            collection_name=settings.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=embedder.get_sentence_embedding_dimension(), distance=Distance.COSINE
            ),
        )
        if not chunks:
            return 0
        vectors = embedder.encode([c["text"] for c in chunks], normalize_embeddings=True).tolist()
        points = [
            PointStruct(id=c["id"], vector=v, payload={"source": c["source"], "text": c["text"]})
            for c, v in zip(chunks, vectors)
        ]
        client.upsert(collection_name=settings.COLLECTION_NAME, points=points)
        return len(points)


def retrieve(query: str, top_k: int = 3) -> str:
    """Sucht die passendsten Lektionsabschnitte und formatiert sie als Kontext."""
    client = get_client()
    if not client.collection_exists(settings.COLLECTION_NAME):
        return ""
    vector = get_embedder().encode(query, normalize_embeddings=True).tolist()
    response = client.query_points(collection_name=settings.COLLECTION_NAME, query=vector, limit=top_k)
    chunks = []
    for hit in response.points:
        source = hit.payload.get("source", "curriculum")
        chunks.append(f"Source: {source} (Score: {hit.score:.2f})\n{hit.payload.get('text', '')}")
    return "\n\n---\n\n".join(chunks)
