"""Kommandozeilen-Wrapper: baut den Qdrant-Index aus curriculum/*.md neu auf."""
import rag


def build_index() -> None:
    count = rag.build_index()
    if count:
        print(f"Successfully indexed {count} curriculum chunks into Qdrant.")
    else:
        print("No Markdown content found to index.")


if __name__ == "__main__":
    try:
        build_index()
    except RuntimeError as e:
        raise SystemExit(str(e))
