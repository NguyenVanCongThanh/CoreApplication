"""
ai-service/app/core/llm.py
LLM wrapper:
  - CHAT      → Anthropic (claude-3-5-haiku / sonnet)
  - EMBEDDING → FastEmbed (ONNX, runs in-process, no server needed)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic
from fastembed import TextEmbedding

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Client singletons ─────────────────────────────────────────────────────────

_anthropic: anthropic.AsyncAnthropic | None = None
_embed_model: TextEmbedding | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic


def get_embed_model() -> TextEmbedding:
    global _embed_model
    if _embed_model is None:
        # Model tự download lần đầu (~130MB), cache vào /root/.cache/fastembed
        _embed_model = TextEmbedding(model_name=settings.embedding_model)
    return _embed_model


# ── Embedding (FastEmbed — chạy in-process, không cần server) ─────────────────

async def create_embedding(text: str) -> list[float]:
    """Single text → embedding vector via FastEmbed."""
    import asyncio
    text = text.replace("\n", " ").strip()
    if not text:
        return [0.0] * settings.embedding_dimensions

    model = get_embed_model()
    # FastEmbed là sync, chạy trong thread pool để không block event loop
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None, lambda: list(model.embed([text]))
    )
    return embeddings[0].tolist()


async def create_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Batch embedding via FastEmbed."""
    import asyncio
    cleaned = [t.replace("\n", " ").strip() or " " for t in texts]
    model = get_embed_model()
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None, lambda: list(model.embed(cleaned))
    )
    return [e.tolist() for e in embeddings]


# ── Chat (Anthropic) — giữ nguyên ────────────────────────────────────────────

async def chat_complete(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str:
    client = get_anthropic_client()

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


def _extract_json(raw: str) -> dict | list:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fenced = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    fenced = re.sub(r"\s*```\s*$", "", fenced, flags=re.MULTILINE).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass
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
    raw = await chat_complete(
        messages=messages, model=model,
        temperature=temperature, max_tokens=max_tokens,
    )
    try:
        return _extract_json(raw)
    except ValueError as e:
        logger.error(f"JSON parse error: {e}")
        raise


# ── Prompt Templates — giữ nguyên (copy từ file gốc) ─────────────────────────

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
    question_text: str, wrong_answer: str, correct_answer: str,
    context_chunks: list[str], language: str = "vi",
) -> list[dict]:
    context = "\n---\n".join(f"[Đoạn {i+1}] {c}" for i, c in enumerate(context_chunks))
    if language == "vi":
        user_msg = f"""TÀI LIỆU THAM KHẢO:\n{context}\n\n---\nCÂU HỎI: {question_text}\nĐÁP ÁN ĐÚNG: {correct_answer}\nHỌC SINH TRẢ LỜI: {wrong_answer}\n\nPhân tích lỗi và trả về JSON:\n{{"explanation": "...","gap_type": "misconception | missing_prerequisite | careless | other","knowledge_gap": "...","study_suggestion": "...","confidence": 0.0}}"""
    else:
        user_msg = f"""REFERENCE MATERIAL:\n{context}\n\n---\nQUESTION: {question_text}\nCORRECT ANSWER: {correct_answer}\nSTUDENT ANSWERED: {wrong_answer}\n\nAnalyze the error and return JSON:\n{{"explanation": "...","gap_type": "misconception | missing_prerequisite | careless | other","knowledge_gap": "...","study_suggestion": "...","confidence": 0.0}}"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_TUTOR[language]},
        {"role": "user", "content": user_msg},
    ]


def build_quiz_generation_prompt(
    bloom_level: str, context_chunks: list[str], node_name: str,
    language: str = "vi", existing_questions: list[str] | None = None,
) -> list[dict]:
    context = "\n---\n".join(f"[Nguồn {i+1}] {c}" for i, c in enumerate(context_chunks))
    existing = ""
    if existing_questions:
        existing = "\n\nTRÁNH TRÙNG VỚI:\n" + "\n".join(f"- {q}" for q in existing_questions[:5])
    bloom_desc = {
        "remember": ("Nhớ", "Remember"), "understand": ("Hiểu", "Understand"),
        "apply": ("Vận dụng", "Apply"), "analyze": ("Phân tích", "Analyze"),
        "evaluate": ("Đánh giá", "Evaluate"), "create": ("Sáng tạo", "Create"),
    }
    bloom_vi, bloom_en = bloom_desc.get(bloom_level, ("Nhớ", "Remember"))
    if language == "vi":
        user_msg = f"""TÀI LIỆU:\n{context}{existing}\n\nCHỦ ĐỀ: {node_name}\nCẤP ĐỘ BLOOM: {bloom_vi} ({bloom_level})\n\nTạo 1 câu hỏi trắc nghiệm. Trả về JSON:\n{{"question_text":"...","bloom_level":"{bloom_level}","question_type":"SINGLE_CHOICE","answer_options":[{{"text":"...","is_correct":true,"explanation":"..."}},{{"text":"...","is_correct":false,"explanation":"..."}},{{"text":"...","is_correct":false,"explanation":"..."}},{{"text":"...","is_correct":false,"explanation":"..."}}],"explanation":"...","source_quote":"..."}}"""
    else:
        user_msg = f"""MATERIAL:\n{context}{existing}\n\nTOPIC: {node_name}\nBLOOM LEVEL: {bloom_en}\n\nCreate 1 multiple choice question. Return JSON:\n{{"question_text":"...","bloom_level":"{bloom_level}","question_type":"SINGLE_CHOICE","answer_options":[{{"text":"...","is_correct":true,"explanation":"..."}},{{"text":"...","is_correct":false,"explanation":"..."}},{{"text":"...","is_correct":false,"explanation":"..."}},{{"text":"...","is_correct":false,"explanation":"..."}}],"explanation":"...","source_quote":"..."}}"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT_QUIZ_GEN[language]},
        {"role": "user", "content": user_msg},
    ]