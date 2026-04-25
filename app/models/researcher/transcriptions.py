"""Audio Transcription Models - AI transcription features."""
from datetime import datetime
from app.database import db


class AudioTranscription(db.Model):
    """Audio file transcriptions (like SciSpace's AI Transcribe)"""
    __tablename__ = 'audio_transcriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # File info
    original_filename = db.Column(db.String(500))
    file_path = db.Column(db.String(1000))  # Stored audio file
    file_size_bytes = db.Column(db.BigInteger)
    duration_seconds = db.Column(db.Integer)
    audio_format = db.Column(db.String(50))  # mp3, mp4, m4a, wav, webm
    
    # Transcription settings
    source_language = db.Column(db.String(10), default='auto')  # 'en', 'es', 'fr', 'auto'
    target_language = db.Column(db.String(10), default='en')
    audio_description = db.Column(db.Text)  # Optional context for AI
    
    # Results
    transcript_text = db.Column(db.Text)
    transcript_json = db.Column(db.JSON)  # Timestamped segments
    confidence_score = db.Column(db.Float)
    
    # Processing
    status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    error_message = db.Column(db.Text)
    processing_time_ms = db.Column(db.Integer)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    project = db.relationship('ResearchProject', backref='transcriptions')
    user = db.relationship('User', backref='transcriptions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'original_filename': self.original_filename,
            'duration_seconds': self.duration_seconds,
            'audio_format': self.audio_format,
            'source_language': self.source_language,
            'status': self.status,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class TranscriptionSegment(db.Model):
    """Timestamped transcript segments for playback sync"""
    __tablename__ = 'transcription_segments'
    
    id = db.Column(db.Integer, primary_key=True)
    transcription_id = db.Column(db.Integer, db.ForeignKey('audio_transcriptions.id'), nullable=False)
    
    start_time_ms = db.Column(db.Integer)  # Milliseconds
    end_time_ms = db.Column(db.Integer)
    text = db.Column(db.Text)
    speaker_id = db.Column(db.String(50))  # For speaker diarization
    confidence = db.Column(db.Float)
    
    transcription = db.relationship('AudioTranscription', backref='segments')
    
    def to_dict(self):
        return {
            'id': self.id,
            'start_time_ms': self.start_time_ms,
            'end_time_ms': self.end_time_ms,
            'text': self.text,
            'speaker_id': self.speaker_id,
            'confidence': self.confidence,
        }


class TranscriptionAnnotation(db.Model):
    """User annotations on transcriptions"""
    __tablename__ = 'transcription_annotations'
    
    id = db.Column(db.Integer, primary_key=True)
    transcription_id = db.Column(db.Integer, db.ForeignKey('audio_transcriptions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    start_time_ms = db.Column(db.Integer)
    end_time_ms = db.Column(db.Integer)
    annotation_text = db.Column(db.Text)
    code_id = db.Column(db.Integer, db.ForeignKey('researcher_codes.id'))  # Link to coding system
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    transcription = db.relationship('AudioTranscription', backref='annotations')
    user = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'transcription_id': self.transcription_id,
            'start_time_ms': self.start_time_ms,
            'end_time_ms': self.end_time_ms,
            'annotation_text': self.annotation_text,
            'code_id': self.code_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
