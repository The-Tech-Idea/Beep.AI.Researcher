"""User Preferences & Settings."""
from datetime import datetime
from app.core.time_utils import utcnow_naive
from app.database import db


class UserPreferences(db.Model):
    """User UI/UX preferences"""
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Theme & Display
    theme = db.Column(db.String(20), default='dark')  # 'dark', 'light', 'system'
    font_size = db.Column(db.String(20), default='medium')  # 'small', 'medium', 'large'
    editor_theme = db.Column(db.String(50), default='monokai')
    sidebar_collapsed = db.Column(db.Boolean, default=False)
    
    # AI Settings
    ai_creativity_default = db.Column(db.String(50), default='balanced')
    ai_max_tokens_default = db.Column(db.Integer, default=1500)
    ai_language_preference = db.Column(db.String(10), default='en')
    
    # Notifications
    email_notifications = db.Column(db.Boolean, default=True)
    browser_notifications = db.Column(db.Boolean, default=True)
    collaboration_alerts = db.Column(db.Boolean, default=True)
    
    # Defaults
    default_workbook_id = db.Column(db.Integer, db.ForeignKey('ai_workbooks.id'))
    
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    user = db.relationship('User', backref=db.backref('preferences', uselist=False))
    
    def to_dict(self):
        return {
            'theme': self.theme,
            'font_size': self.font_size,
            'editor_theme': self.editor_theme,
            'sidebar_collapsed': self.sidebar_collapsed,
            'ai_creativity_default': self.ai_creativity_default,
            'ai_max_tokens_default': self.ai_max_tokens_default,
            'ai_language_preference': self.ai_language_preference,
            'email_notifications': self.email_notifications,
            'browser_notifications': self.browser_notifications,
            'collaboration_alerts': self.collaboration_alerts,
        }
