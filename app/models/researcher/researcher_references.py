"""Bibliographic Reference model for research projects (Phase 4.1)."""
import json
from enum import Enum
from typing import List, Dict, Optional

from app.database import db
from app.core.time_utils import utcnow_naive


class ReferenceSourceType(Enum):
    """Reference source type enumeration."""
    JOURNAL = "journal"
    BOOK = "book"
    WEBSITE = "website"
    CONFERENCE = "conference"
    THESIS = "thesis"
    REPORT = "report"
    ARXIV = "arxiv"
    PUBMED = "pubmed"
    OTHER = "other"


class Reference(db.Model):
    """Bibliographic reference with citation formatting support."""
    __tablename__ = 'references'
    __table_args__ = (
        db.UniqueConstraint('project_id', 'citation_key', name='uq_ref_citation_key'),
        db.Index('ix_references_project_id', 'project_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'))
    
    # Core bibliographic fields
    title = db.Column(db.String(512), nullable=False, index=True)
    authors_json = db.Column(db.Text)  # JSON array of author names
    year = db.Column(db.Integer)
    source = db.Column(db.String(512))  # Journal name, publisher, website domain, etc.
    source_type = db.Column(db.String(50), default=ReferenceSourceType.OTHER.value)
    
    # Identifiers
    doi = db.Column(db.String(255), index=True)  # Digital Object Identifier
    pubmed_id = db.Column(db.String(50), index=True)  # PMID for PubMed articles
    arxiv_id = db.Column(db.String(50), index=True)  # arXiv ID
    isbn = db.Column(db.String(20))  # ISBN for books
    issn = db.Column(db.String(20))  # ISSN for journals
    url = db.Column(db.String(512))  # Direct URL to article/resource
    citation_key = db.Column(db.String(255), nullable=False, index=True)  # BibTeX key
    
    # Extended bibliographic fields
    abstract = db.Column(db.Text)  # Paper abstract
    keywords_json = db.Column(db.Text)  # JSON array of keywords
    volume = db.Column(db.String(50))  # Journal volume
    issue = db.Column(db.String(50))  # Journal issue
    pages = db.Column(db.String(50))  # Page range
    
    # Publication metadata
    published_date = db.Column(db.DateTime)  # Full publication date
    accessed_date = db.Column(db.DateTime)  # Date accessed (for websites)
    
    # Extensible metadata
    metadata_json = db.Column(db.Text)  # JSON for additional fields
    
    # Additional fields for compatibility
    publication = db.Column(db.String(256))  # Alias for source (backward compat)
    citation = db.Column(db.Text)  # Formatted citation
    notes = db.Column(db.Text)  # User notes
    
    # Statistics
    citation_count = db.Column(db.Integer, default=0)  # Number of documents citing this reference
    last_citation_date = db.Column(db.DateTime)  # Last time a document linked to this reference
    
    created_at = db.Column(db.DateTime, default=utcnow_naive, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    project = db.relationship('ResearchProject', backref='references_list')
    document = db.relationship('ResearcherDocument', backref='references')
    document_links = db.relationship('DocumentReference', backref='reference', cascade='all, delete-orphan')
    
    def __repr__(self):
        """String representation."""
        return f"<Reference: {self.citation_key} ({self.year})>"
    
    # JSON field helpers
    
    def get_authors(self) -> List[str]:
        """Get authors as list."""
        if self.authors_json:
            return json.loads(self.authors_json)
        return []
    
    def set_authors(self, value: List[str]):
        """Set authors from list."""
        self.authors_json = json.dumps(value) if value else None
    
    def get_keywords(self) -> List[str]:
        """Get keywords as list."""
        if self.keywords_json:
            return json.loads(self.keywords_json)
        return []
    
    def set_keywords(self, value: List[str]):
        """Set keywords from list."""
        self.keywords_json = json.dumps(value) if value else None
    
    def get_metadata_dict(self) -> Dict:
        """Get metadata as dictionary."""
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return {}
    
    def set_metadata_dict(self, value: Dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(value) if value else None
    
    # Citation format conversions
    
    def to_bibtex(self) -> str:
        """Convert to BibTeX format."""
        authors_str = " and ".join(self.get_authors()) if self.get_authors() else "Unknown"
        bibtex = f"@{self.source_type}{{{self.citation_key},\n"
        bibtex += f"  title = {{{self.title}}},\n"
        bibtex += f"  author = {{{authors_str}}},\n"
        
        if self.year:
            bibtex += f"  year = {{{self.year}}},\n"
        if self.source:
            if self.source_type == ReferenceSourceType.JOURNAL.value:
                bibtex += f"  journal = {{{self.source}}},\n"
            elif self.source_type == ReferenceSourceType.BOOK.value:
                bibtex += f"  publisher = {{{self.source}}},\n"
        if self.volume:
            bibtex += f"  volume = {{{self.volume}}},\n"
        if self.issue:
            bibtex += f"  number = {{{self.issue}}},\n"
        if self.pages:
            bibtex += f"  pages = {{{self.pages}}},\n"
        if self.doi:
            bibtex += f"  doi = {{{self.doi}}},\n"
        if self.url:
            bibtex += f"  url = {{{self.url}}},\n"
        
        bibtex += "}"
        return bibtex
    
    def to_ris(self) -> str:
        """Convert to RIS format."""
        type_map = {
            ReferenceSourceType.JOURNAL.value: "JOUR",
            ReferenceSourceType.BOOK.value: "BOOK",
            ReferenceSourceType.CONFERENCE.value: "CONF",
            ReferenceSourceType.THESIS.value: "THES",
            ReferenceSourceType.REPORT.value: "RPRT",
            ReferenceSourceType.WEBSITE.value: "ELEC",
            ReferenceSourceType.PUBMED.value: "JOUR",
            ReferenceSourceType.ARXIV.value: "JOUR",
        }
        
        ris = f"TY  - {type_map.get(self.source_type, 'MISC')}\n"
        ris += f"TI  - {self.title}\n"
        
        for author in self.get_authors():
            ris += f"AU  - {author}\n"
        
        if self.year:
            ris += f"PY  - {self.year}\n"
        if self.source:
            ris += f"JO  - {self.source}\n"
        if self.volume:
            ris += f"VL  - {self.volume}\n"
        if self.issue:
            ris += f"IS  - {self.issue}\n"
        if self.pages:
            ris += f"SP  - {self.pages.split('-')[0].strip()}\n"
            if '-' in self.pages:
                ris += f"EP  - {self.pages.split('-')[1].strip()}\n"
        if self.doi:
            ris += f"DO  - {self.doi}\n"
        if self.url:
            ris += f"UR  - {self.url}\n"
        if self.abstract:
            ris += f"AB  - {self.abstract}\n"
        for keyword in self.get_keywords():
            ris += f"KW  - {keyword}\n"
        
        ris += "ER  - \n"
        return ris
    
    def to_apa(self) -> str:
        """Convert to APA citation format."""
        citation = ""
        
        authors = self.get_authors()
        if authors:
            if len(authors) == 1:
                citation += f"{authors[0]}"
            elif len(authors) == 2:
                citation += f"{authors[0]} & {authors[1]}"
            else:
                citation += f"{authors[0]} et al."
        else:
            citation += "Unknown"
        
        if self.year:
            citation += f" ({self.year})."
        else:
            citation += " (n.d.)."
        
        citation += f" {self.title}."
        
        if self.source_type == ReferenceSourceType.JOURNAL.value:
            citation += f" {self.source}"
            if self.volume:
                citation += f", {self.volume}"
            if self.issue:
                citation += f"({self.issue})"
            if self.pages:
                citation += f", {self.pages}"
        elif self.source_type == ReferenceSourceType.BOOK.value:
            citation += f" {self.source}."
        
        if self.doi:
            citation += f" https://doi.org/{self.doi}"
        elif self.url:
            citation += f" Retrieved from {self.url}"
        
        return citation
    
    def to_mla(self) -> str:
        """Convert to MLA citation format."""
        citation = ""
        
        authors = self.get_authors()
        if authors:
            citation += authors[0]
            if len(authors) > 1:
                authors_rest = ", and ".join(authors[1:])
                citation += f", and {authors_rest}"
        else:
            citation += "Unknown"
        
        citation += f". \"{self.title}.\""
        
        if self.source_type == ReferenceSourceType.JOURNAL.value:
            citation += f" {self.source}"
            if self.volume:
                citation += f", vol. {self.volume}"
            if self.issue:
                citation += f", no. {self.issue}"
            if self.year:
                citation += f", {self.year}"
            if self.pages:
                citation += f", pp. {self.pages}"
        elif self.source_type == ReferenceSourceType.BOOK.value:
            citation += f" {self.source}"
            if self.year:
                citation += f", {self.year}"
        
        citation += "."
        
        if self.doi:
            citation += f" https://doi.org/{self.doi}."
        elif self.url:
            citation += f" Web. {self.url}."
        
        return citation
    
    def to_chicago(self) -> str:
        """Convert to Chicago citation format."""
        citation = ""
        
        authors = self.get_authors()
        if authors:
            authors_str = ", ".join(authors)
            citation += authors_str
        else:
            citation += "Unknown"
        
        citation += f". {self.title}."
        
        if self.source_type == ReferenceSourceType.JOURNAL.value:
            citation += f" {self.source}"
            if self.volume:
                citation += f" {self.volume}"
            if self.issue:
                citation += f", no. {self.issue}"
        elif self.source_type == ReferenceSourceType.BOOK.value:
            citation += f" {self.source}"
        
        if self.year:
            citation += f" ({self.year})"
        
        if self.pages:
            citation += f": {self.pages}"
        
        citation += "."
        
        return citation
    
    def to_json(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "document_id": self.document_id,
            "title": self.title,
            "authors": self.get_authors(),
            "year": self.year,
            "source": self.source,
            "source_type": self.source_type,
            "doi": self.doi,
            "pubmed_id": self.pubmed_id,
            "arxiv_id": self.arxiv_id,
            "isbn": self.isbn,
            "issn": self.issn,
            "url": self.url,
            "citation_key": self.citation_key,
            "abstract": self.abstract,
            "keywords": self.get_keywords(),
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "accessed_date": self.accessed_date.isoformat() if self.accessed_date else None,
            "metadata": self.get_metadata_dict(),
            "citation_count": self.citation_count,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    def to_dict(self) -> Dict:
        """Convert to dictionary (alias for to_json)."""
        return self.to_json()
    
    @staticmethod
    def from_json(data: Dict) -> 'Reference':
        """Create Reference from JSON dictionary."""
        ref = Reference()
        ref.title = data.get("title")
        ref.citation_key = data.get("citation_key")
        ref.project_id = data.get("project_id")
        ref.document_id = data.get("document_id")
        
        if "authors" in data:
            ref.set_authors(data["authors"] if isinstance(data["authors"], list) else [data["authors"]])
        
        ref.year = data.get("year")
        ref.source = data.get("source")
        ref.source_type = data.get("source_type", ReferenceSourceType.OTHER.value)
        ref.doi = data.get("doi")
        ref.pubmed_id = data.get("pubmed_id")
        ref.arxiv_id = data.get("arxiv_id")
        ref.isbn = data.get("isbn")
        ref.issn = data.get("issn")
        ref.url = data.get("url")
        ref.abstract = data.get("abstract")
        ref.notes = data.get("notes")
        
        if "keywords" in data:
            ref.set_keywords(data["keywords"] if isinstance(data["keywords"], list) else [data["keywords"]])
        
        ref.volume = data.get("volume")
        ref.issue = data.get("issue")
        ref.pages = data.get("pages")
        
        if "metadata" in data and isinstance(data["metadata"], dict):
            ref.set_metadata_dict(data["metadata"])
        
        return ref


class DocumentReference(db.Model):
    """Linking model for documents that cite references."""
    __tablename__ = 'document_references'
    __table_args__ = (
        db.UniqueConstraint('document_id', 'reference_id', name='uq_doc_ref'),
        db.Index('ix_document_references_document_id', 'document_id'),
        db.Index('ix_document_references_reference_id', 'reference_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'), nullable=False)
    reference_id = db.Column(db.Integer, db.ForeignKey('references.id'), nullable=False)
    
    # Citation context
    citation_context = db.Column(db.Text)  # Where/how the reference is cited
    citation_count = db.Column(db.Integer, default=1)  # How many times cited
    
    # Citation strength/confidence (0.0-1.0)
    confidence = db.Column(db.Float, default=1.0)
    
    # Citation type
    citation_type = db.Column(db.String(50), default="direct")  # direct | indirect | mentioned
    
    created_at = db.Column(db.DateTime, default=utcnow_naive, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    document = db.relationship('ResearcherDocument', backref='reference_links')
    
    def __repr__(self):
        """String representation."""
        return f"<DocumentReference: doc_id={self.document_id} -> ref_id={self.reference_id}>"
    
    def to_json(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "reference_id": self.reference_id,
            "citation_context": self.citation_context,
            "citation_count": self.citation_count,
            "confidence": self.confidence,
            "citation_type": self.citation_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    def to_dict(self) -> Dict:
        """Convert to dictionary (alias for to_json)."""
        return self.to_json()

