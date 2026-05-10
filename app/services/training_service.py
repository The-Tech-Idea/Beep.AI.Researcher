from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.database import db
from app.models.researcher import (
    Flashcard,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    ResearcherDocument,
)

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 600
_MAX_CHUNKS_PER_DOC = 5


def chunk_text(text, size=200):
    if not text:
        return []
    chunks = []
    for index in range(0, len(text), size):
        chunks.append((text[index : index + size], f"chunk-{index}"))
    return chunks


def extract_json_list(text: str, key: str) -> list:
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data.get(key) or []
    except (json.JSONDecodeError, AttributeError):
        pass
    return []


def generate_flashcards(
    project,
    data: dict[str, Any],
    *,
    user_id=None,
    beep_ai_client_module,
    build_project_grounded_context_fn,
    build_grounded_user_prompt_fn,
    merge_supporting_sources_fn,
    resolve_project_generation_temperature_fn,
):
    document_ids = data.get("document_ids") or []
    limit = min(int(data.get("limit", 10)), 50)
    chunk_size = min(int(data.get("chunk_size", _CHUNK_SIZE)), 2000)

    documents_query = ResearcherDocument.query.filter_by(project_id=project.id)
    if document_ids:
        documents_query = documents_query.filter(
            ResearcherDocument.id.in_(document_ids)
        )
    documents = documents_query.limit(10).all()

    created = []
    generation_temperature = resolve_project_generation_temperature_fn(project)
    supporting_sources = []

    if beep_ai_client_module.is_configured():
        system_prompt = (
            "You are a study assistant. Given a research text excerpt, generate clear "
            "question-and-answer flashcards that test understanding of key facts and concepts. "
            'Respond with valid JSON: {"cards": [{"front": "...", "back": "..."}]}'
        )

        for document in documents:
            if len(created) >= limit:
                break
            if not document.text_content:
                continue

            grounded_context = build_project_grounded_context_fn(
                project,
                document.text_content[: min(chunk_size, 1200)],
                user_id=user_id,
                max_results=3,
                max_chars_per_result=260,
            )

            chunks = chunk_text(document.text_content, chunk_size)[:_MAX_CHUNKS_PER_DOC]
            for chunk_value, chunk_id in chunks:
                if len(created) >= limit:
                    break
                remaining = limit - len(created)
                user_prompt = (
                    f'TEXT:\n"""{chunk_value.strip()}"""\n\n'
                    f"Generate {min(remaining, 3)} flashcards from this text."
                )
                user_prompt = build_grounded_user_prompt_fn(
                    user_prompt,
                    grounded_context,
                    "Use the study text as the primary source and stay within the supporting library evidence below.",
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                ok, reply = beep_ai_client_module.chat_reply(
                    messages, temperature=generation_temperature
                )
                if not ok:
                    logger.warning(
                        "Flashcard LLM failed for doc %s: %s", document.id, reply
                    )
                    continue

                cards = extract_json_list(reply, "cards")
                for card in cards:
                    front = (card.get("front") or "").strip()
                    back = (card.get("back") or "").strip()
                    if not front or not back:
                        continue
                    try:
                        flashcard = Flashcard(
                            project_id=project.id,
                            document_id=document.id,
                            front=front,
                            back=back,
                            source_chunk_id=chunk_id,
                        )
                        db.session.add(flashcard)
                        db.session.flush()
                        created.append(
                            {
                                "id": flashcard.id,
                                "front": flashcard.front,
                                "back": flashcard.back,
                                "document_id": document.id,
                                "document_name": document.name,
                                "source_chunk_id": chunk_id,
                            }
                        )
                    except Exception as exc:
                        db.session.rollback()
                        logger.error("Error saving flashcard: %s", exc)

                    if len(created) >= limit:
                        break
                supporting_sources = merge_supporting_sources_fn(
                    supporting_sources, grounded_context
                )

        if created:
            db.session.commit()
            return {
                "flashcards": created,
                "method": "llm",
                "supporting_sources": supporting_sources,
            }, 200

    for document in documents:
        if not document.text_content or len(created) >= limit:
            continue
        chunks = chunk_text(document.text_content, 150)
        for text, chunk_id in chunks[:1]:
            if len(created) >= limit:
                break
            flashcard = Flashcard(
                project_id=project.id,
                document_id=document.id,
                front=text[:80] + ("..." if len(text) > 80 else "") + " ?",
                back=text[:200] + ("..." if len(text) > 200 else ""),
                source_chunk_id=chunk_id,
            )
            db.session.add(flashcard)
            db.session.flush()
            created.append(
                {
                    "id": flashcard.id,
                    "front": flashcard.front,
                    "back": flashcard.back,
                    "document_id": document.id,
                    "document_name": document.name,
                    "source_chunk_id": chunk_id,
                }
            )

    db.session.commit()
    return {
        "flashcards": created,
        "method": "heuristic",
        "note": "Study cards were created directly from your file text because the assisted study service is unavailable right now.",
        "supporting_sources": [],
    }, 200


def list_flashcards(project):
    cards = (
        Flashcard.query.filter_by(project_id=project.id)
        .order_by(Flashcard.created_at.desc())
        .limit(200)
        .all()
    )
    return {"flashcards": [card.to_dict() for card in cards]}, 200


def generate_quiz(
    project,
    data: dict[str, Any],
    *,
    user_id=None,
    beep_ai_client_module,
    build_project_grounded_context_fn,
    build_grounded_user_prompt_fn,
    merge_supporting_sources_fn,
    resolve_project_generation_temperature_fn,
):
    name = (data.get("name") or "Quiz").strip()
    document_ids = data.get("document_ids") or []
    limit = min(int(data.get("limit", 5)), 30)
    chunk_size = min(int(data.get("chunk_size", _CHUNK_SIZE)), 2000)

    documents_query = ResearcherDocument.query.filter_by(project_id=project.id)
    if document_ids:
        documents_query = documents_query.filter(
            ResearcherDocument.id.in_(document_ids)
        )
    documents = documents_query.limit(limit).all()

    quiz = Quiz(project_id=project.id, name=name)
    db.session.add(quiz)
    db.session.flush()

    questions_created = 0
    generation_temperature = resolve_project_generation_temperature_fn(project)
    supporting_sources = []

    if beep_ai_client_module.is_configured():
        system_prompt = (
            "You are an exam question writer. Given a research text excerpt, create "
            "multiple-choice questions (MCQ) with 4 answer choices and one correct answer. "
            "Questions must test factual comprehension of the text. "
            'Respond with valid JSON:\n{"questions": [{"question": "...", "options": ["A","B","C","D"], '
            '"correct_index": 0, "explanation": "..."}]}'
        )

        for document in documents:
            if questions_created >= limit:
                break
            if not document.text_content:
                continue

            grounded_context = build_project_grounded_context_fn(
                project,
                document.text_content[: min(chunk_size, 1200)],
                user_id=user_id,
                max_results=3,
                max_chars_per_result=260,
            )

            chunks = chunk_text(document.text_content, chunk_size)[:_MAX_CHUNKS_PER_DOC]
            for chunk_value, chunk_id in chunks:
                if questions_created >= limit:
                    break
                remaining = limit - questions_created
                user_prompt = (
                    f'TEXT:\n"""{chunk_value.strip()}"""\n\n'
                    f"Generate {min(remaining, 2)} MCQ questions from this text."
                )
                user_prompt = build_grounded_user_prompt_fn(
                    user_prompt,
                    grounded_context,
                    "Use the study text as the primary source and keep every question supported by the library evidence below.",
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                ok, reply = beep_ai_client_module.chat_reply(
                    messages, temperature=generation_temperature
                )
                if not ok:
                    logger.warning("Quiz LLM failed for doc %s: %s", document.id, reply)
                    continue

                question_list = extract_json_list(reply, "questions")
                for question_data in question_list:
                    question_text = (question_data.get("question") or "").strip()
                    options = question_data.get("options") or []
                    correct_index = question_data.get("correct_index", 0)

                    if not question_text or len(options) < 2:
                        continue
                    if not isinstance(
                        correct_index, int
                    ) or not 0 <= correct_index < len(options):
                        correct_index = 0

                    try:
                        question = QuizQuestion(
                            quiz_id=quiz.id,
                            question=question_text,
                            options_json=json.dumps(options[:4]),
                            correct_index=correct_index,
                            source_chunk_id=chunk_id,
                        )
                        db.session.add(question)
                        questions_created += 1
                    except Exception as exc:
                        db.session.rollback()
                        logger.error("Error saving quiz question: %s", exc)

                    if questions_created >= limit:
                        break
                supporting_sources = merge_supporting_sources_fn(
                    supporting_sources, grounded_context
                )

        if questions_created > 0:
            db.session.commit()
            return {
                "quiz_id": quiz.id,
                "name": quiz.name,
                "question_count": questions_created,
                "method": "llm",
                "supporting_sources": supporting_sources,
            }, 201

    for document in documents:
        if not document.text_content or questions_created >= limit:
            continue
        text = document.text_content[:100].strip()
        if not text:
            continue
        question = QuizQuestion(
            quiz_id=quiz.id,
            question=f'What is the main point of: "{text}..."?',
            options_json=json.dumps(
                ["Option A", "Option B", "Option C", "See document"]
            ),
            correct_index=3,
            source_chunk_id="chunk-0",
        )
        db.session.add(question)
        questions_created += 1

    db.session.commit()
    return {
        "quiz_id": quiz.id,
        "name": quiz.name,
        "question_count": questions_created,
        "method": "heuristic",
        "note": "The quiz was created directly from your file text because the assisted study service is unavailable right now.",
        "supporting_sources": [],
    }, 201


def list_quizzes(project):
    quizzes = (
        Quiz.query.filter_by(project_id=project.id)
        .order_by(Quiz.created_at.desc())
        .all()
    )
    return {"quizzes": [quiz.to_dict() for quiz in quizzes]}, 200


def get_quiz(project, quiz_id):
    quiz = Quiz.query.filter_by(project_id=project.id, id=quiz_id).first_or_404()
    questions = []
    for question in quiz.questions:
        options = json.loads(question.options_json) if question.options_json else []
        questions.append(
            {
                "id": question.id,
                "question": question.question,
                "options": options,
                "correct_index": question.correct_index,
            }
        )
    return {"quiz": {"id": quiz.id, "name": quiz.name}, "questions": questions}, 200


def delete_flashcard(project, card_id):
    card = Flashcard.query.filter_by(project_id=project.id, id=card_id).first_or_404()
    db.session.delete(card)
    db.session.commit()
    return {"deleted": True, "id": card_id}, 200


def delete_quiz(project, quiz_id):
    quiz = Quiz.query.filter_by(project_id=project.id, id=quiz_id).first_or_404()
    db.session.delete(quiz)
    db.session.commit()
    return {"deleted": True, "id": quiz_id}, 200


def submit_quiz(project, quiz_id, data: dict[str, Any], *, user_id=None):
    quiz = Quiz.query.filter_by(project_id=project.id, id=quiz_id).first_or_404()
    answers = data.get("answers") or []
    questions_by_id = {question.id: question for question in quiz.questions}
    results = []
    score = 0

    for answer in answers:
        question_id = answer.get("question_id")
        selected = answer.get("selected")
        question = questions_by_id.get(question_id)
        if question is None:
            continue
        correct = selected == question.correct_index
        if correct:
            score += 1
        results.append(
            {
                "question_id": question_id,
                "selected": selected,
                "correct_index": question.correct_index,
                "correct": correct,
            }
        )

    total = len(quiz.questions)
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user_id,
        score=score,
        total=total,
        answers_json=json.dumps(results),
    )
    db.session.add(attempt)
    db.session.commit()

    return {
        "score": score,
        "total": total,
        "percentage": round(score / total * 100, 1) if total else 0,
        "results": results,
        "attempt_id": attempt.id,
    }, 200


class TrainingService:
    """Phase 4: per-document flashcard generation and creation."""

    def generate_flashcards_from_text(self, text: str, *, count: int = 6) -> list[dict]:
        """Generate flashcards from raw text without requiring a project context.

        Returns a list of {"question": ..., "answer": ...} dicts.
        """
        from app.services import beep_ai_client

        if not beep_ai_client.is_configured():
            return self._heuristic_flashcards(text, count)

        system_prompt = (
            "You are a study assistant. Given a research text excerpt, generate clear "
            "question-and-answer flashcards that test understanding of key facts and concepts. "
            'Respond with valid JSON: {"cards": [{"front": "...", "back": "..."}]}'
        )
        user_content = (
            f'TEXT:\n"""{text[:4000].strip()}"""\n\n'
            f"Generate {count} flashcards from this text."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        ok, reply = beep_ai_client.chat_reply(messages, temperature=0.5)
        if not ok:
            return self._heuristic_flashcards(text, count)

        cards = extract_json_list(reply, "cards")
        result = []
        for card in cards[:count]:
            front = (card.get("front") or "").strip()
            back = (card.get("back") or "").strip()
            if front and back:
                result.append({"question": front, "answer": back})
        return result or self._heuristic_flashcards(text, count)

    @staticmethod
    def _heuristic_flashcards(text: str, count: int) -> list[dict]:
        """Fallback: create simple flashcards from sentence chunks."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
        result = []
        for i, sent in enumerate(sentences[:count]):
            result.append(
                {
                    "question": f"What does the text say about: {sent[:60]}...?",
                    "answer": sent[:200],
                }
            )
        return result

    @staticmethod
    def create_flashcard(project_id: int, document_id: int, question: str, answer: str):
        """Create and persist a Flashcard record."""
        flashcard = Flashcard(
            project_id=project_id,
            document_id=document_id,
            front=question,
            back=answer,
            source_chunk_id="manual",
        )
        db.session.add(flashcard)
        db.session.commit()
        return flashcard
