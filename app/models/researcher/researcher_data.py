"""Julius-style: ResearcherDataSource, SavedChart models."""
from datetime import datetime
from app.core.time_utils import utcnow_naive
from app.database import db


class ResearcherDataSource(db.Model):
    """Julius-style: structured data source (XLSX, CSV)."""
    __tablename__ = 'researcher_data_sources'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # xlsx | csv
    file_path = db.Column(db.String(512), nullable=False)
    table_name = db.Column(db.String(255))  # sheet name for XLSX
    last_synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='data_sources')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'name': self.name,
            'type': self.type, 'table_name': self.table_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SavedChart(db.Model):
    """Julius-style: saved chart/visualization."""
    __tablename__ = 'saved_charts'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    chart_type = db.Column(db.String(50), nullable=False)  # bar | line | pie | heatmap
    config_json = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='saved_charts')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'name': self.name,
            'chart_type': self.chart_type, 'config_json': self.config_json,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ScheduledReport(db.Model):
    """Julius-style: scheduled report delivery."""
    __tablename__ = 'scheduled_reports'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    schedule_cron = db.Column(db.String(100), default='0 9 * * 1')  # e.g. Mondays 9am
    recipients_json = db.Column(db.Text, default='[]')  # JSON array of emails
    report_config_json = db.Column(db.Text)  # Queries, chart IDs
    is_active = db.Column(db.Boolean, default=True)
    last_run_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='scheduled_reports')

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'name': self.name,
            'schedule_cron': self.schedule_cron, 'is_active': self.is_active,
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
        }
