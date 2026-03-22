"""
ai-service/app/services/chunker.py
Splits documents (PDF, text, video transcript) into overlapping chunks.
Preserves metadata for Deep Link (page number, video timestamp).
Handles bilingual content (VI/EN).
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    text: str
    index: int
    source_type: str           # 'document' | 'video'
    page_number: int | None = None
    start_time_sec: int | None = None
    end_time_sec: int | None = None
    language: str = "vi"


def sanitize_text(text: str) -> str:
    """
    Remove characters PostgreSQL UTF-8 cannot store.
    - Null bytes (0x00): extracted by PyMuPDF from some PDFs
    - Other non-printable control chars (keep \\n \\r \\t which are fine)
    """
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


class PDFChunker:
    """
    Chunk PDF files page-by-page, then split large pages into smaller chunks.
    Preserves page_number for Deep Link.
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_bytes(self, pdf_bytes: bytes) -> list[DocumentChunk]:
        """Process raw PDF bytes → list of chunks with page metadata."""
        try:
            import pymupdf  # PyMuPDF (faster, better table support)
            return self._chunk_with_pymupdf(pdf_bytes)
        except ImportError:
            logger.warning("PyMuPDF not available, falling back to pypdf")
            try:
                import pypdf
                return self._chunk_with_pypdf(pdf_bytes)
            except ImportError:
                logger.error("No PDF library available")
                return []

    def _chunk_with_pymupdf(self, pdf_bytes: bytes) -> list[DocumentChunk]:
        import pymupdf
        chunks: list[DocumentChunk] = []
        chunk_index = 0

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = sanitize_text(page.get_text("text").strip())
            if not text:
                continue

            page_chunks = self._split_text(text)
            for chunk_text in page_chunks:
                chunk_text = sanitize_text(chunk_text.strip())
                if chunk_text:
                    chunks.append(DocumentChunk(
                        text=chunk_text,
                        index=chunk_index,
                        source_type="document",
                        page_number=page_num + 1,
                        language=detect_language(chunk_text),
                    ))
                    chunk_index += 1

        doc.close()
        return chunks

    def _chunk_with_pypdf(self, pdf_bytes: bytes) -> list[DocumentChunk]:
        import pypdf
        chunks: list[DocumentChunk] = []
        chunk_index = 0

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        for page_num, page in enumerate(reader.pages):
            text = sanitize_text((page.extract_text() or "").strip())
            if not text:
                continue

            page_chunks = self._split_text(text)
            for chunk_text in page_chunks:
                chunk_text = sanitize_text(chunk_text.strip())
                if chunk_text:
                    chunks.append(DocumentChunk(
                        text=chunk_text,
                        index=chunk_index,
                        source_type="document",
                        page_number=page_num + 1,
                        language=detect_language(chunk_text),
                    ))
                    chunk_index += 1

        return chunks

    def _split_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks at sentence boundaries.
        Prefers sentence breaks over hard character cuts.
        """
        if len(text) <= self.chunk_size:
            return [text]

        # Split into sentences (handles both VI and EN punctuation)
        sentences = re.split(r'(?<=[.!?。！？\n])\s+', text)
        chunks: list[str] = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) <= self.chunk_size:
                current = (current + " " + sentence).strip()
            else:
                if current:
                    chunks.append(current)
                # Start new chunk with overlap from previous
                if current and self.overlap > 0:
                    words = current.split()
                    overlap_text = " ".join(words[-self.overlap // 5:])  # last ~10 words
                    current = (overlap_text + " " + sentence).strip()
                else:
                    current = sentence

        if current:
            chunks.append(current)

        return chunks


class DocxChunker(PDFChunker):
    """Chunk Word (.docx) files."""

    def chunk_bytes(self, docx_bytes: bytes) -> list[DocumentChunk]:
        try:
            from docx import Document
            doc = Document(io.BytesIO(docx_bytes))
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text.strip())
            
            # Also extract from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            full_text.append(cell.text.strip())

            text = "\n".join(full_text)
            raw_chunks = self._split_text(text)
            
            return [
                DocumentChunk(
                    text=sanitize_text(c),
                    index=i,
                    source_type="document",
                    page_number=1, # docx doesn't easily provide page numbers
                    language=detect_language(c)
                )
                for i, c in enumerate(raw_chunks)
            ]
        except Exception as e:
            logger.error(f"Error chunking docx: {e}")
            return []


class PptxChunker(PDFChunker):
    """Chunk PowerPoint (.pptx) files."""

    def chunk_bytes(self, pptx_bytes: bytes) -> list[DocumentChunk]:
        try:
            from pptx import Presentation
            prs = Presentation(io.BytesIO(pptx_bytes))
            chunks: list[DocumentChunk] = []
            chunk_index = 0

            for i, slide in enumerate(prs.slides):
                slide_text = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text.strip())
                
                # Also notes
                if slide.has_notes_slide:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
                    if notes:
                        slide_text.append(notes)
                
                text = "\n".join(slide_text)
                if not text:
                    continue

                slide_chunks = self._split_text(text)
                for c_text in slide_chunks:
                    chunks.append(DocumentChunk(
                        text=sanitize_text(c_text),
                        index=chunk_index,
                        source_type="document",
                        page_number=i + 1,  # slide number as page number
                        language=detect_language(c_text)
                    ))
                    chunk_index += 1
            return chunks
        except Exception as e:
            logger.error(f"Error chunking pptx: {e}")
            return []


class ExcelChunker(PDFChunker):
    """Chunk Excel (.xlsx, .xls) files."""

    def chunk_bytes(self, excel_bytes: bytes) -> list[DocumentChunk]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
            full_text = []
            for sheet in wb.worksheets:
                full_text.append(f"Sheet: {sheet.title}")
                for row in sheet.iter_rows(values_only=True):
                    row_text = [str(cell) for cell in row if cell is not None]
                    if row_text:
                        full_text.append(" | ".join(row_text))
            
            text = "\n".join(full_text)
            raw_chunks = self._split_text(text)
            
            return [
                DocumentChunk(
                    text=sanitize_text(c),
                    index=i,
                    source_type="document",
                    page_number=1,
                    language=detect_language(c)
                )
                for i, c in enumerate(raw_chunks)
            ]
        except Exception as e:
            logger.error(f"Error chunking excel: {e}")
            return []


class VideoTranscriptChunker:
    """
    Chunk video transcripts with timestamp metadata.
    Supports Whisper-style transcripts (SRT or JSON with timestamps).
    Groups segments into ~2-minute chunks for meaningful context.
    """

    def __init__(self, segment_duration_sec: int = 120, overlap_sec: int = 15):
        self.segment_duration = segment_duration_sec
        self.overlap = overlap_sec

    def chunk_whisper_json(self, transcript: dict) -> list[DocumentChunk]:
        """
        Process Whisper JSON transcript:
        {"segments": [{"start": 0.0, "end": 5.2, "text": "..."}, ...]}
        """
        segments = transcript.get("segments", [])
        if not segments:
            return []

        chunks: list[DocumentChunk] = []
        chunk_index = 0
        current_text = ""
        current_start = segments[0]["start"]
        current_end = segments[0]["end"]

        for seg in segments:
            segment_text = sanitize_text(seg.get("text", "").strip())
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", seg_start)

            # If adding this segment exceeds the chunk duration, flush
            if seg_end - current_start > self.segment_duration and current_text:
                chunks.append(DocumentChunk(
                    text=current_text.strip(),
                    index=chunk_index,
                    source_type="video",
                    start_time_sec=int(current_start),
                    end_time_sec=int(current_end),
                    language=detect_language(current_text),
                ))
                chunk_index += 1
                overlap_start = max(current_start, seg_end - self.overlap)
                current_text = segment_text
                current_start = overlap_start
                current_end = seg_end
            else:
                current_text = (current_text + " " + segment_text).strip()
                current_end = seg_end

        # Flush last chunk
        if current_text.strip():
            chunks.append(DocumentChunk(
                text=current_text.strip(),
                index=chunk_index,
                source_type="video",
                start_time_sec=int(current_start),
                end_time_sec=int(current_end),
                language=detect_language(current_text),
            ))

        return chunks

    def chunk_srt(self, srt_content: str) -> list[DocumentChunk]:
        """Parse SRT format and chunk by duration."""
        blocks = re.split(r"\n\n+", srt_content.strip())
        segments = []
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 2:
                continue
            for line in lines:
                match = re.match(
                    r"(\d{2}):(\d{2}):(\d{2}),(\d+)\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d+)",
                    line,
                )
                if match:
                    h1, m1, s1, ms1, h2, m2, s2, ms2 = match.groups()
                    start = int(h1)*3600 + int(m1)*60 + int(s1)
                    end = int(h2)*3600 + int(m2)*60 + int(s2)
                    text_lines = [l for l in lines if not l.isdigit() and "-->" not in l]
                    text = sanitize_text(" ".join(text_lines).strip())
                    if text:
                        segments.append({"start": start, "end": end, "text": text})
                    break

        return self.chunk_whisper_json({"segments": segments})


def detect_language(text: str) -> str:
    """
    Simple language detection: if >30% of characters are Vietnamese-specific
    diacritics, classify as Vietnamese.
    """
    vi_chars = set("àáảãạăắặằẳẵâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ"
                   "ÀÁẢÃẠĂẮẶẰẲẴÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ")
    total = len([c for c in text if c.isalpha()])
    if total == 0:
        return "vi"
    vi_count = sum(1 for c in text if c in vi_chars)
    return "vi" if vi_count / total > 0.05 else "en"


def format_timestamp(seconds: int) -> str:
    """Convert seconds to MM:SS or HH:MM:SS string."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
