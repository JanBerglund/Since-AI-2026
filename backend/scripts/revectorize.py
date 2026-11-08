"""Rebuild the rule embedding index from clauses.json."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from retrieval import PVAGRetriever


def main() -> None:
    clauses_path = BACKEND_ROOT / "data/clauses.json"
    embeddings_path = BACKEND_ROOT / "data/embeddings.npy"
    retriever = PVAGRetriever(
        clauses_path=clauses_path,
        embeddings_path=embeddings_path,
        rebuild=True,
    )
    print(f"Rebuilt {len(retriever.clauses)} rule embeddings at {embeddings_path}")


if __name__ == "__main__":
    main()
