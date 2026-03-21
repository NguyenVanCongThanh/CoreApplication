"""
ai-service/app/core/llm.py
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from groq import AsyncGroq
from fastembed import TextEmbedding

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Client singletons ─────────────────────────────────────────────────────────

_groq: AsyncGroq | None = None
_embed_model: TextEmbedding | None = None


def get_groq_client() -> AsyncGroq:
    global _groq
    if _groq is None:
        _groq = AsyncGroq(api_key=settings.groq_api_key)
    return _groq


def get_embed_model() -> TextEmbedding:
    global _embed_model
    if _embed_model is None:
        _embed_model = TextEmbedding(model_name=settings.embedding_model)
    return _embed_model


# ── Embedding (FastEmbed — local, no server needed) ───────────────────────────

async def create_embedding(text: str) -> list[float]:
    import asyncio
    text = text.replace("\n", " ").strip()
    if not text:
        return [0.0] * settings.embedding_dimensions

    model = get_embed_model()
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None, lambda: list(model.embed([text]))
    )
    return embeddings[0].tolist()


async def create_embeddings_batch(texts: list[str]) -> list[list[float]]:
    import asyncio
    cleaned = [t.replace("\n", " ").strip() or " " for t in texts]
    model = get_embed_model()
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None, lambda: list(model.embed(cleaned))
    )
    return [e.tolist() for e in embeddings]


# ── Chat (Groq) ────────────────────────────────────────────────────────────────

async def chat_complete(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    json_mode: bool = False,
) -> str:
    """
    Gọi Groq API với messages format chuẩn OpenAI.
    Groq hỗ trợ system message trực tiếp (không cần tách như Anthropic).
    """
    client = get_groq_client()
    
    kwargs: dict[str, Any] = {
        "model": model or settings.chat_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise


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
    """
    Gọi với JSON mode
    """
    raw = await chat_complete(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )
    try:
        return _extract_json(raw)
    except ValueError as e:
        logger.error(f"JSON parse error: {e}\nRaw: {raw[:300]}")
        raise


# ── System Prompts ─────────────────────────────────────────────────────────────

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
    distractor_options: list[str],
    context_chunks: list[str],
    language: str = "vi",
) -> list[dict]:
    context = "\n---\n".join(f"[Đoạn {i+1}] {c}" for i, c in enumerate(context_chunks))
    distractors_text = "\n".join(f"  - {d}" for d in distractor_options) if distractor_options else "Không có"
    
    if language == "vi":
        user_msg = (
            f"TÀI LIỆU THAM KHẢO:\n{context}\n\n---\n"
            f"CÂU HỎI: {question_text}\n"
            f"ĐÁP ÁN ĐÚNG: {correct_answer}\n"
            f"CÁC ĐÁP ÁN NHIỄU:\n{distractors_text}\n"
            f"HỌC SINH TRẢ LỜI: {wrong_answer}\n\n"
            f"Phân tích TẠI SAO sinh viên chọn \"{wrong_answer}\" thay vì đáp án đúng. "
            f"Chỉ ra sự nhầm lẫn cụ thể giữa đáp án sinh viên chọn và đáp án đúng. "
            f"Đánh giá các tài liệu tham khảo được cho (Đoạn 1, Đoạn 2,...). Trả về relevant_source_indices là mảng chứa các số thứ tự của các đoạn THỰC SỰ liên quan đến việc vá lỗ hổng kiến thức của học sinh. Trả về mảng rỗng [] nếu không có đoạn nào liên quan.\n"
            f"Trả về JSON:\n"
            f'{{"explanation": "...","gap_type": "misconception | missing_prerequisite | careless | other",'
            f'"knowledge_gap": "...","study_suggestion": "...","confidence": 0.0, "relevant_source_indices": [1]}}'
        )
    else:
        user_msg = (
            f"REFERENCE MATERIAL:\n{context}\n\n---\n"
            f"QUESTION: {question_text}\n"
            f"CORRECT ANSWER: {correct_answer}\n"
            f"DISTRACTOR OPTIONS:\n{distractors_text}\n"
            f"STUDENT ANSWERED: {wrong_answer}\n\n"
            f"Analyze WHY student chose \"{wrong_answer}\" instead of correct answer. "
            f"Identify the specific confusion between the student's answer and the correct answer. "
            f"Evaluate the provided reference materials ([Đoạn 1], [Đoạn 2],...). Return relevant_source_indices as an array of the indices of the segments that are ACTUALLY relevant to fixing the student's knowledge gap. Return an empty array [] if none are relevant.\n"
            f"Return JSON:\n"
            f'{{"explanation": "...","gap_type": "misconception | missing_prerequisite | careless | other",'
            f'"knowledge_gap": "...","study_suggestion": "...","confidence": 0.0, "relevant_source_indices": [1]}}'
        )
    
    return [
        {"role": "system", "content": SYSTEM_PROMPT_TUTOR[language]},
        {"role": "user", "content": user_msg},
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
        "remember":   ("Nhớ",       "Remember"),
        "understand": ("Hiểu",      "Understand"),
        "apply":      ("Vận dụng",  "Apply"),
        "analyze":    ("Phân tích", "Analyze"),
        "evaluate":   ("Đánh giá",  "Evaluate"),
        "create":     ("Sáng tạo",  "Create"),
    }
    bloom_vi, bloom_en = bloom_desc.get(bloom_level, ("Nhớ", "Remember"))
    
    schema = (
        '{"question_text":"...","bloom_level":"' + bloom_level + '",'
        '"question_type":"SINGLE_CHOICE",'
        '"answer_options":['
        '{"text":"...","is_correct":true,"explanation":"..."},'
        '{"text":"...","is_correct":false,"explanation":"..."},'
        '{"text":"...","is_correct":false,"explanation":"..."},'
        '{"text":"...","is_correct":false,"explanation":"..."}'
        '],"explanation":"...","source_quote":"..."}'
    )
    
    if language == "vi":
        user_msg = (
            f"TÀI LIỆU:\n{context}{existing}\n\n"
            f"CHỦ ĐỀ: {node_name}\n"
            f"CẤP ĐỘ BLOOM: {bloom_vi} ({bloom_level})\n\n"
            f"Tạo 1 câu hỏi trắc nghiệm. Trả về JSON:\n{schema}"
        )
    else:
        user_msg = (
            f"MATERIAL:\n{context}{existing}\n\n"
            f"TOPIC: {node_name}\n"
            f"BLOOM LEVEL: {bloom_en}\n\n"
            f"Create 1 multiple choice question. Return JSON:\n{schema}"
        )
    
    return [
        {"role": "system", "content": SYSTEM_PROMPT_QUIZ_GEN[language]},
        {"role": "user", "content": user_msg},
    ]


SYSTEM_PROMPT_FLASHCARD_GEN = {
    "vi": (
        "Bạn là chuyên gia tạo Flashcard học tập theo phương pháp Spaced Repetition. "
        "Hãy tạo các flashcard ngắn gọn, tập trung vào khái niệm cốt lõi, "
        "đặc biệt chú ý khắc phục các lỗi sai phổ biến của học sinh. "
        "Chỉ trả về JSON hợp lệ theo đúng schema, không thêm text khác."
    ),
    "en": (
        "You are an expert at creating study flashcards for Spaced Repetition. "
        "Create concise flashcards focusing on core concepts, "
        "paying special attention to correcting common student misconceptions. "
        "Return ONLY valid JSON matching the requested schema exactly."
    ),
}

def build_flashcard_generation_prompt(
    context_chunks: list[str],
    node_name: str,
    wrong_answers_context: str,
    count: int = 3,
    language: str = "vi",
    existing_fronts: list[str] | None = None,
) -> list[dict]:
    context = "\n---\n".join(f"[Nguồn {i+1}] {c}" for i, c in enumerate(context_chunks))
    
    schema = (
        '{"flashcards":['
        '{"front_text":"[Câu hỏi ngắn gọn hoặc khái niệm]","back_text":"[Câu trả lời hoặc giải thích ngắn gọn]"},'
        '{"front_text":"...","back_text":"..."}'
        ']}'
    )
    
    existing_avoidance = ""
    if existing_fronts:
        existing_list = "\n".join(f"- {front}" for front in existing_fronts[:10])
        if language == "vi":
            existing_avoidance = f"\nTRÁNH TRÙNG LẶP VỚI CÁC FLASHCARD HIỆN CÓ (Bạn phải tạo nội dung HOÀN TOÀN MỚI):\n{existing_list}\n"
        else:
            existing_avoidance = f"\nDO NOT DUPLICATE THESE EXISTING FLASHCARDS (You must create ENTIRELY NEW content):\n{existing_list}\n"
    
    if language == "vi":
        user_msg = (
            f"TÀI LIỆU:\n{context}\n\n"
            f"CHỦ ĐỀ: {node_name}\n"
            f"LỖI SAI GẦN ĐÂY CỦA HỌC SINH (Hãy tập trung khắc phục):\n{wrong_answers_context}\n"
            f"{existing_avoidance}\n"
            f"Số lượng flashcard cần tạo mới: {count}\n"
            f"Tạo {count} flashcard MỚI. Trả về JSON:\n{schema}"
        )
    else:
        user_msg = (
            f"MATERIAL:\n{context}\n\n"
            f"TOPIC: {node_name}\n"
            f"RECENT STUDENT ERRORS (Focus on correcting these):\n{wrong_answers_context}\n"
            f"{existing_avoidance}\n"
            f"Count to generate: {count}\n"
            f"Create {count} NEW flashcards. Return JSON:\n{schema}"
        )
    
    return [
        {"role": "system", "content": SYSTEM_PROMPT_FLASHCARD_GEN[language]},
        {"role": "user", "content": user_msg},
    ]