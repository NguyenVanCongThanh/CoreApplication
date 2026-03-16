"""
ai-service/app/core/llm.py
LLM wrapper:
  - CHAT      → Anthropic (claude-3-5-haiku / sonnet)
  - EMBEDDING → Ollama native SDK (nomic-embed-text, 768 dims)

Ollama native SDK supports batch embedding in a single call:
    client.embed(model=..., input=["text1", "text2", ...])
→ returns embeddings: list[list[float]]
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic
import ollama as ollama_sdk

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Client singletons ─────────────────────────────────────────────────────────

_anthropic: anthropic.AsyncAnthropic | None = None
_ollama: ollama_sdk.AsyncClient | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic


def get_ollama_client() -> ollama_sdk.AsyncClient:
    global _ollama
    if _ollama is None:
        _ollama = ollama_sdk.AsyncClient(host=settings.ollama_host)
    return _ollama


# ── Embedding (Ollama) ────────────────────────────────────────────────────────

async def create_embedding(text: str) -> list[float]:
    """Single text → embedding vector via Ollama."""
    text = text.replace("\n", " ").strip()
    if not text:
        return [0.0] * settings.embedding_dimensions

    client = get_ollama_client()
    response = await client.embed(
        model=settings.embedding_model,
        input=text,
    )
    return response.embeddings[0]


async def create_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Batch embedding in a single Ollama API call.
    Ollama's /api/embed accepts a list as `input` directly.
    """
    client = get_ollama_client()
    cleaned = [t.replace("\n", " ").strip() or " " for t in texts]

    response = await client.embed(
        model=settings.embedding_model,
        input=cleaned,
    )
    return response.embeddings


# ── Chat (Anthropic) ──────────────────────────────────────────────────────────

async def chat_complete(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    json_mode: bool = False,  # kept for API compatibility, handled via prompt
) -> str:
    """
    Chat completion via Anthropic.
    Anthropic doesn't have a json_mode flag — we rely on prompt-level instruction
    and _extract_json() for parsing.
    """
    client = get_anthropic_client()

    # Anthropic separates system prompt from the messages array
    system_parts: list[str] = []
    converted: list[dict] = []
    for msg in messages:
        if msg["role"] == "system":
            system_parts.append(msg["content"])
        else:
            converted.append({"role": msg["role"], "content": msg["content"]})

    system = "\n\n".join(system_parts) if system_parts else anthropic.NOT_GIVEN

    kwargs: dict[str, Any] = {
        "model": model or settings.chat_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": converted,
        "system": system,
    }

    response = await client.messages.create(**kwargs)
    return response.content[0].text


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict | list:
    """
    Robust JSON extraction from LLM output.
    Handles: pure JSON, ```json...``` fences, JSON embedded in prose.
    """
    raw = raw.strip()

    # 1. Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown fences
    fenced = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    fenced = re.sub(r"\s*```\s*$", "", fenced, flags=re.MULTILINE).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass

    # 3. Find first {...} or [...] block (greedy)
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    raise ValueError(f"LLM returned non-JSON output:\n{raw[:400]}")


async def chat_complete_json(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> dict | list:
    """Structured JSON output from Anthropic."""
    raw = await chat_complete(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    try:
        return _extract_json(raw)
    except ValueError as e:
        logger.error(f"JSON parse error (Anthropic): {e}")
        raise


# ── Prompt Templates (bilingual VI/EN) ───────────────────────────────────────

SYSTEM_PROMPT_TUTOR = {
    "vi": (
        "Bạn là một gia sư AI thông minh, chuyên phân tích lỗi học sinh và đưa ra giải thích "
        "dựa trên tài liệu giảng dạy chính thức. Hãy trả lời ngắn gọn, chính xác và bằng tiếng Việt. "
        "Luôn dẫn nguồn từ tài liệu được cung cấp. Chỉ trả về JSON hợp lệ, không thêm text khác."
    ),
    "en": (
        "You are an intelligent AI tutor specializing in diagnosing student errors. "
        "Base all explanations strictly on the provided course materials. "
        "Return ONLY valid JSON, no additional text or markdown."
    ),
}

SYSTEM_PROMPT_QUIZ_GEN = {
    "vi": (
        "Bạn là chuyên gia thiết kế câu hỏi kiểm tra theo thang Bloom's Taxonomy. "
        "Tạo câu hỏi chất lượng cao, bám sát tài liệu gốc. "
        "Chỉ trả về JSON hợp lệ theo đúng schema, không thêm text khác."
    ),
    "en": (
        "You are an expert at designing assessments following Bloom's Taxonomy. "
        "Create high-quality questions grounded strictly in source material. "
        "Return ONLY valid JSON matching the requested schema exactly."
    ),
}


def build_diagnosis_prompt(
    question_text: str,
    wrong_answer: str,
    correct_answer: str,
    context_chunks: list[str],
    language: str = "vi",
) -> list[dict]:
    context = "\n---\n".join(f"[Đoạn {i+1}] {c}" for i, c in enumerate(context_chunks))

    if language == "vi":
        user_msg = f"""TÀI LIỆU THAM KHẢO:
{context}

---
CÂU HỎI: {question_text}
ĐÁP ÁN ĐÚNG: {correct_answer}
HỌC SINH TRẢ LỜI: {wrong_answer}

Phân tích lỗi và trả về JSON:
{{
  "explanation": "Giải thích ngắn gọn (2-4 câu)",
  "gap_type": "misconception | missing_prerequisite | careless | other",
  "knowledge_gap": "Tên kiến thức còn thiếu",
  "study_suggestion": "Gợi ý ôn tập cụ thể",
  "confidence": 0.0
}}"""
    else:
        user_msg = f"""REFERENCE MATERIAL:
{context}

---
QUESTION: {question_text}
CORRECT ANSWER: {correct_answer}
STUDENT ANSWERED: {wrong_answer}

Analyze the error and return JSON:
{{
  "explanation": "Brief explanation (2-4 sentences)",
  "gap_type": "misconception | missing_prerequisite | careless | other",
  "knowledge_gap": "Name of missing concept",
  "study_suggestion": "Specific study recommendation",
  "confidence": 0.0
}}"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT_TUTOR[language]},
        {"role": "user",   "content": user_msg},
    ]


def build_quiz_generation_prompt(
    bloom_level: str,
    context_chunks: list[str],
    node_name: str,
    language: str = "vi",
    existing_questions: list[str] | None = None,
) -> list[dict]:
    context = "\n---\n".join(f"[Nguồn {i+1}] {c}" for i, c in enumerate(context_chunks))
    existing = ""
    if existing_questions:
        existing = "\n\nTRÁNH TRÙNG VỚI:\n" + "\n".join(f"- {q}" for q in existing_questions[:5])

    bloom_desc = {
        "remember":   ("Nhớ",       "Remember — recall facts"),
        "understand": ("Hiểu",      "Understand — explain concepts"),
        "apply":      ("Vận dụng",  "Apply — use in new situations"),
        "analyze":    ("Phân tích", "Analyze — draw connections"),
        "evaluate":   ("Đánh giá",  "Evaluate — justify decisions"),
        "create":     ("Sáng tạo",  "Create — produce original work"),
    }
    bloom_vi, bloom_en = bloom_desc.get(bloom_level, ("Nhớ", "Remember"))

    if language == "vi":
        user_msg = f"""TÀI LIỆU:
{context}
{existing}

CHỦ ĐỀ: {node_name}
CẤP ĐỘ BLOOM: {bloom_vi} ({bloom_level})

Tạo 1 câu hỏi trắc nghiệm. Trả về JSON:
{{
  "question_text": "...",
  "bloom_level": "{bloom_level}",
  "question_type": "SINGLE_CHOICE",
  "answer_options": [
    {{"text": "...", "is_correct": true,  "explanation": "..."}},
    {{"text": "...", "is_correct": false, "explanation": "..."}},
    {{"text": "...", "is_correct": false, "explanation": "..."}},
    {{"text": "...", "is_correct": false, "explanation": "..."}}
  ],
  "explanation": "...",
  "source_quote": "Trích nguyên văn ≤100 ký tự"
}}"""
    else:
        user_msg = f"""MATERIAL:
{context}
{existing}

TOPIC: {node_name}
BLOOM LEVEL: {bloom_en}

Create 1 multiple choice question. Return JSON:
{{
  "question_text": "...",
  "bloom_level": "{bloom_level}",
  "question_type": "SINGLE_CHOICE",
  "answer_options": [
    {{"text": "...", "is_correct": true,  "explanation": "..."}},
    {{"text": "...", "is_correct": false, "explanation": "..."}},
    {{"text": "...", "is_correct": false, "explanation": "..."}},
    {{"text": "...", "is_correct": false, "explanation": "..."}}
  ],
  "explanation": "...",
  "source_quote": "Exact quote ≤100 chars"
}}"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT_QUIZ_GEN[language]},
        {"role": "user",   "content": user_msg},
    ]