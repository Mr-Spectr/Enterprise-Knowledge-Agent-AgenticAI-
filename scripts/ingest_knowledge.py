"""Index one explicitly approved RAG document.

Example: python scripts/ingest_knowledge.py handbook.pdf --access-level student
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge_base import ingest_document  # noqa: E402

parser = argparse.ArgumentParser(description="Index an approved PDF, DOCX, TXT, or Markdown document.")
parser.add_argument("document")
parser.add_argument("--access-level", choices=["public", "student", "faculty", "admin"], default="public")
args = parser.parse_args()
print(ingest_document(args.document, args.access_level))
