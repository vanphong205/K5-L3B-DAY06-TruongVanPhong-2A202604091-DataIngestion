"""Quick check for the Ollama embedding provider."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from src.embeddings import OllamaEmbedder

def main() -> None:
    model_name = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Testing Ollama embedder (model: {model_name or 'default from .env'})...")
    
    try:
        embedder = OllamaEmbedder(model_name=model_name)
        print(f" Connected successfully!")
        print(f"  - Model: {embedder.model_name}")
        print(f"  - Dimensions: {embedder.dimensions}")
        
        # Test query embedding
        query = "Quy trình cứu hộ xe điện VinFast VF 8 khi xảy ra va chạm"
        vec = embedder.embed_query(query)
        print(f" Query vector shape: {len(vec)}, preview: {vec[:3]}...")
        
        # Test document embedding
        docs = [
            "Pin cao áp được đặt dưới sàn xe.",
            "Cần ngắt cầu chì cứu hộ trước khi tiếp cận khối pin."
        ]
        doc_vecs = embedder.embed_documents(docs)
        print(f" Embedded {len(doc_vecs)} documents successfully!")
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\n Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
