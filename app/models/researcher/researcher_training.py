"""Anara-style: Flashcard, Quiz, QuizQuestion, QuizAttempt."""
import json

from app.database import db
from app.core.time_utils import utcnow_naive


class Flashcard(db.Model):
    """Anara-style: flashcard generated from docs."""
    __tablename__ = 'researcher_flashcards'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'))
    front = db.Column(db.Text, nullable=False)
    back = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), default='medium')  # easy | medium | hard
    source_chunk_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='flashcards')
    document = db.relationship('ResearcherDocument', backref='flashcards')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id,
            'document_id': self.document_id,
            'document_name': self.document.name if self.document else None,
            'front': self.front, 'back': self.back,
            'difficulty': self.difficulty or 'medium',
            'source_chunk_id': self.source_chunk_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Quiz(db.Model):
    """Anara-style: MCQ quiz generated from docs."""
    __tablename__ = 'researcher_quizzes'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='quizzes')
    questions = db.relationship('QuizQuestion', backref='quiz', cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', backref='quiz', cascade='all, delete-orphan')

    def to_dict(self):
        best = None
        if self.attempts:
            best = max((a.score / a.total * 100 if a.total else 0) for a in self.attempts)
        return {
            'id': self.id, 'name': self.name,
            'question_count': len(self.questions),
            'best_score': round(best, 1) if best is not None else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class QuizQuestion(db.Model):
    """Single MCQ in a quiz."""
    __tablename__ = 'researcher_quiz_questions'

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('researcher_quizzes.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=False)  # ["A", "B", "C", "D"]
    correct_index = db.Column(db.Integer, nullable=False)  # 0-based
    source_chunk_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    def to_dict(self):
        return {
            'id': self.id, 'quiz_id': self.quiz_id,
            'question': self.question,
            'options': json.loads(self.options_json) if self.options_json else [],
            'correct_index': self.correct_index,
        }


class QuizAttempt(db.Model):
    """Track user quiz scores."""
    __tablename__ = 'researcher_quiz_attempts'

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('researcher_quizzes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    answers_json = db.Column(db.Text)  # [{"question_id":1,"selected":2,"correct":true}]
    completed_at = db.Column(db.DateTime, default=utcnow_naive)

    def to_dict(self):
        return {
            'id': self.id, 'quiz_id': self.quiz_id,
            'score': self.score, 'total': self.total,
            'percentage': round(self.score / self.total * 100, 1) if self.total else 0,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

