"""Integration DB models — credentials, project integrations, webhook subscriptions."""
from app.database import db
from app.core.time_utils import utcnow_naive


class IntegrationCredential(db.Model):
    """Per-user encrypted credentials for external services."""
    __tablename__ = 'integration_credentials'
    __table_args__ = (db.UniqueConstraint('user_id', 'integration_type',
                                          name='uq_user_integration'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    integration_type = db.Column(db.String(50), nullable=False)   # google_drive, zotero, etc.
    encrypted_data = db.Column(db.Text, nullable=False)           # Fernet-encrypted JSON
    display_name = db.Column(db.String(100))
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    user = db.relationship('User', backref='integration_credentials')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'integration_type': self.integration_type,
            'display_name': self.display_name,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ProjectIntegration(db.Model):
    """Per-project integration enablement."""
    __tablename__ = 'project_integrations'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    integration_type = db.Column(db.String(50), nullable=False)
    credential_id = db.Column(db.Integer, db.ForeignKey('integration_credentials.id'))
    config_json = db.Column(db.Text, default='{}')
    enabled = db.Column(db.Boolean, default=True)
    last_sync_at = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='idle')   # idle, syncing, success, error
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='integrations')
    credential = db.relationship('IntegrationCredential', backref='project_integrations')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'integration_type': self.integration_type,
            'credential_id': self.credential_id,
            'enabled': self.enabled,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'sync_status': self.sync_status,
        }


class WebhookSubscription(db.Model):
    """Outbound webhook subscriptions per project."""
    __tablename__ = 'webhook_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    secret = db.Column(db.String(100))            # HMAC signing key
    events = db.Column(db.Text, nullable=False)   # JSON array of event types
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='webhooks')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'url': self.url,
            'events': self.events,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WebhookDelivery(db.Model):
    """Webhook delivery log."""
    __tablename__ = 'webhook_deliveries'

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('webhook_subscriptions.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    payload_json = db.Column(db.Text)
    response_status = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    delivered_at = db.Column(db.DateTime, default=utcnow_naive)
    success = db.Column(db.Boolean, default=False)

    subscription = db.relationship('WebhookSubscription', backref='deliveries')
