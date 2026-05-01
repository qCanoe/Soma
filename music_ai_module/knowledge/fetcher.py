"""Fetch remote HTML, strip to text, and chunk with overlap."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import List, Tuple
from urllib.request import Request, urlopen

from .schemas import SourceChunk
from .sources import SourceRecord


def fetch_html(url: str, timeout_s: int = 45) -> str:
    req = Request(url, headers={"User-Agent": "MindWave-KnowledgeBot/1.0"})
    with urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("beautifulsoup4 is required — pip install beautifulsoup4") from exc

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(
    full_text: str,
    source: SourceRecord,
    chunk_size: int,
    overlap: int,
) -> List[SourceChunk]:
    """Split plain text into overlapping chunks with global char offsets."""
    chunks: List[SourceChunk] = []
    if not full_text:
        return chunks
    n = len(full_text)
    start = 0
    idx = 0
    while start < n:
        end = min(start + chunk_size, n)
        span = full_text[start:end].strip()
        if span:
            cid = f"{source.id}_chunk_{idx}_{uuid.uuid4().hex[:8]}"
            chunks.append(
                SourceChunk(
                    chunk_id=cid,
                    source_id=source.id,
                    url=source.url,
                    text=span,
                    start_char=start,
                    end_char=end,
                    title=source.title or source.id,
                )
            )
            idx += 1
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


def fetch_and_chunk_source(
    source: SourceRecord,
    chunk_size: int,
    overlap: int,
    raw_dir: Path | None = None,
) -> Tuple[str, List[SourceChunk]]:
    """
    Download source, convert to text, optionally save raw snapshot.
    Returns (plain_text, chunks).
    """
    html = fetch_html(source.url)
    if raw_dir is not None and source.full_text_allowed:
        raw_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w\-]+", "_", source.id)[:80]
        (raw_dir / f"{safe}.html").write_text(html, encoding="utf-8")
    text = html_to_text(html)
    return text, chunk_text(text, source, chunk_size, overlap)


def append_chunks_jsonl(path: Path, chunks: List[SourceChunk]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")


def load_chunks_jsonl(path: Path) -> List[SourceChunk]:
    import json

    if not path.is_file():
        return []
    out: List[SourceChunk] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SourceChunk.from_dict(json.loads(line)))
    return out
