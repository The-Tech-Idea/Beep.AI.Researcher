"""Phase 1 — AI Discovery & Personalised Reading Feed models.

Provides:
- ResearchInterestProfile  — declared and inferred topics per user
- FeedRecommendation       — persisted ranked feed results with feedback signals
- ReadingListItem          — personal save list separate from project library
- PaperAlert               — new-paper alert records
"""
from app.core.time_utils import utcnow_naive
from app.database import db


class ResearchInterestProfile(db.Model):
    """One research interest profile per user.

    ``declared_topics``  — list of topic strings the user explicitly chose.
    ``inferred_topics``  — list of ``{topic, score}`` dicts derived from library TF-IDF.
    ``preferred_sources``— list of source keys the user wants to see in the feed,
                           e.g. ``['pubmed', 'arxiv', 'semantic_scholar']``.
    """
    __tablename__ = 'research_interest_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True,
    )

    declared_topics = db.Column(db.JSON, nullable=False, default=list)
    inferred_topics = db.Column(db.JSON, nullable=False, default=list)
    preferred_sources = db.Column(db.JSON, nullable=False, default=list)
    inference_enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'declared_topics': self.declared_topics or [],
            'inferred_topics': self.inferred_topics or [],
            'preferred_sources': self.preferred_sources or [],
            'inference_enabled': self.inference_enabled,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class FeedRecommendation(db.Model):
    """One recommended paper in a user's personalised feed.

    ``external_id``    — canonical identifier: DOI, arXiv ID, or PubMed PMID.
    ``source``         — originating provider: ``'pubmed'``, ``'arxiv'``,
                         ``'semantic_scholar'``, or ``'crossref'``.
    ``source_id``      — provider-native identifier for later metadata lookups.
    ``url``            — canonical provider URL for the paper when available.
    ``publication_date`` — original publication date string from the provider.
    ``doi``            — DOI preserved separately from the canonical external id.
    ``relevance_score``— float [0, 1] larger = more relevant.
    ``reason``         — human-readable explanation of the match.
    ``dismissed``      — True once the user clicks "not interested".
    ``saved``          — True once the user saves it to a list or project.
    ``feed_date``      — calendar date the recommendation was generated; used to
                         partition/expire old feed pages.
    """
    __tablename__ = 'feed_recommendations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    external_id = db.Column(db.String(255), nullable=False)
    title = db.Column(db.Text, nullable=False)
    authors = db.Column(db.JSON, nullable=False, default=list)
    abstract = db.Column(db.Text)
    source = db.Column(db.String(50), nullable=False)
    source_id = db.Column(db.String(255))
    url = db.Column(db.Text)
    publication_date = db.Column(db.String(40))
    doi = db.Column(db.String(255))
    relevance_score = db.Column(db.Float, nullable=False, default=0.0)
    reason = db.Column(db.Text)
    dismissed = db.Column(db.Boolean, nullable=False, default=False)
    saved = db.Column(db.Boolean, nullable=False, default=False)
    feed_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)

    __table_args__ = (
        db.Index('ix_feed_recommendations_user_date_dismissed',
                 'user_id', 'feed_date', 'dismissed'),
        {'sqlite_autoincrement': True},
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'external_id': self.external_id,
            'title': self.title,
            'authors': self.authors or [],
            'abstract': self.abstract,
            'source': self.source,
            'source_id': self.source_id,
            'url': self.url,
            'publication_date': self.publication_date,
            'doi': self.doi,
            'relevance_score': self.relevance_score,
            'reason': self.reason,
            'dismissed': self.dismissed,
            'saved': self.saved,
            'feed_date': self.feed_date.isoformat() if self.feed_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ReadingListItem(db.Model):
    """One item in a user's personal reading list.

    ``reference_id``  — set when the item already exists in the reference library.
    ``external_id``   — DOI / arXiv ID used until (if) the item is imported.
    ``status``        — ``'unread'`` | ``'reading'`` | ``'done'``.
    ``topic_tags``    — list of topic strings for filtering.
    """
    __tablename__ = 'reading_list_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    reference_id = db.Column(
        db.Integer,
        db.ForeignKey('references.id', ondelete='SET NULL'),
        nullable=True,
    )

    external_id = db.Column(db.String(255))
    title = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='unread')
    topic_tags = db.Column(db.JSON, nullable=False, default=list)
    saved_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)

    __table_args__ = (
        db.Index('ix_reading_list_items_user_status', 'user_id', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'reference_id': self.reference_id,
            'external_id': self.external_id,
            'title': self.title,
            'status': self.status,
            'topic_tags': self.topic_tags or [],
            'saved_at': self.saved_at.isoformat() if self.saved_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PaperAlert(db.Model):
    """One alert record for a paper that matched a user's interests.

    ``external_id``  — DOI / arXiv ID of the alerted paper.
    ``source``       — originating provider.
    ``is_read``      — True once the user has opened or dismissed the alert.
    ``alert_date``   — calendar date the alert was generated.
    """
    __tablename__ = 'paper_alerts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    external_id = db.Column(db.String(255), nullable=False)
    title = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(50), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    alert_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)

    __table_args__ = (
        db.Index('ix_paper_alerts_user_read_date',
                 'user_id', 'is_read', 'alert_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'external_id': self.external_id,
            'title': self.title,
            'source': self.source,
            'is_read': self.is_read,
            'alert_date': self.alert_date.isoformat() if self.alert_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
