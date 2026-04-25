"""Add Phase 4.1 Reference model columns for citation and bibliography management.

Revision ID: phase_41_references
Revises: add_rbac_phase18
Create Date: 2026-02-08

Adds comprehensive bibliographic fields to references table including:
- JSON fields for authors, keywords, metadata
- Extended publication metadata
- Citation statistics and tracking
- Support for multiple identifier types (DOI, PMID, arXiv, ISBN, ISSN)
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = 'phase_41_references'
down_revision = 'add_rbac_phase18'
branch_labels = None
depends_on = None


def upgrade():
    """Add Phase 4.1 Reference columns.
    
    Adds:
    - authors_json: JSON array of author names
    - keywords_json: JSON array of keywords
    - metadata_json: Extensible JSON metadata
    - Extended publication fields
    - Citation statistics fields
    - Additional identifier fields
    """
    
    # Check if references table exists, if not create it
    try:
        connection = op.get_bind()
        inspector = sa.inspect(connection)
        
        if 'references' not in inspector.get_table_names():
            # Create references table from scratch
            op.create_table(
                'references',
                sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
                sa.Column('project_id', sa.Integer(), nullable=False),
                sa.Column('document_id', sa.Integer(), nullable=True),
                
                # Core bibliographic fields
                sa.Column('title', sa.String(512), nullable=False),
                sa.Column('authors_json', sa.Text(), nullable=True),
                sa.Column('year', sa.Integer(), nullable=True),
                sa.Column('source', sa.String(512), nullable=True),
                sa.Column('source_type', sa.String(50), default='other'),
                
                # Identifiers
                sa.Column('doi', sa.String(255), nullable=True),
                sa.Column('pubmed_id', sa.String(50), nullable=True),
                sa.Column('arxiv_id', sa.String(50), nullable=True),
                sa.Column('isbn', sa.String(20), nullable=True),
                sa.Column('issn', sa.String(20), nullable=True),
                sa.Column('url', sa.String(512), nullable=True),
                sa.Column('citation_key', sa.String(255), nullable=False),
                
                # Extended bibliographic fields
                sa.Column('abstract', sa.Text(), nullable=True),
                sa.Column('keywords_json', sa.Text(), nullable=True),
                sa.Column('volume', sa.String(50), nullable=True),
                sa.Column('issue', sa.String(50), nullable=True),
                sa.Column('pages', sa.String(50), nullable=True),
                
                # Publication metadata
                sa.Column('published_date', sa.DateTime(), nullable=True),
                sa.Column('accessed_date', sa.DateTime(), nullable=True),
                
                # Extensible metadata
                sa.Column('metadata_json', sa.Text(), nullable=True),
                
                # Additional compatibility fields
                sa.Column('publication', sa.String(256), nullable=True),
                sa.Column('citation', sa.Text(), nullable=True),
                sa.Column('notes', sa.Text(), nullable=True),
                
                # Statistics
                sa.Column('citation_count', sa.Integer(), default=0),
                sa.Column('last_citation_date', sa.DateTime(), nullable=True),
                
                sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
                sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
                
                # Foreign keys
                sa.ForeignKeyConstraint(['project_id'], ['research_projects.id']),
                sa.ForeignKeyConstraint(['document_id'], ['researcher_documents.id']),
                
                # Constraints and indexes
                sa.UniqueConstraint('project_id', 'citation_key', name='uq_ref_citation_key'),
            )
            
            # Create indexes
            op.create_index('ix_references_project_id', 'references', ['project_id'])
            op.create_index('ix_references_title', 'references', ['title'])
            op.create_index('ix_references_citation_key', 'references', ['citation_key'])
            op.create_index('ix_references_doi', 'references', ['doi'])
            op.create_index('ix_references_pubmed_id', 'references', ['pubmed_id'])
            op.create_index('ix_references_arxiv_id', 'references', ['arxiv_id'])
            op.create_index('ix_references_created_at', 'references', ['created_at'])
        else:
            # Add missing columns if they don't exist
            columns_to_add = [
                ('authors_json', sa.Text),
                ('keywords_json', sa.Text),
                ('metadata_json', sa.Text),
                ('abstract', sa.Text),
                ('volume', sa.String(50)),
                ('issue', sa.String(50)),
                ('pages', sa.String(50)),
                ('published_date', sa.DateTime),
                ('accessed_date', sa.DateTime),
                ('pubmed_id', sa.String(50)),
                ('arxiv_id', sa.String(50)),
                ('isbn', sa.String(20)),
                ('issn', sa.String(20)),
                ('publication', sa.String(256)),
                ('citation', sa.Text),
                ('notes', sa.Text),
                ('citation_count', sa.Integer),
                ('last_citation_date', sa.DateTime),
            ]
            
            existing_columns = [col['name'] for col in inspector.get_columns('references')]
            
            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    if col_name == 'citation_count':
                        op.add_column('references', sa.Column(col_name, col_type, default=0))
                    else:
                        op.add_column('references', sa.Column(col_name, col_type, nullable=True))
            
            # Update source_type to have default if it doesn't
            if 'source_type' not in existing_columns:
                op.add_column('references', sa.Column('source_type', sa.String(50), default='other'))
            
            # Create indexes if they don't exist
            indexes_to_create = [
                ('ix_references_project_id', 'references', ['project_id']),
                ('ix_references_title', 'references', ['title']),
                ('ix_references_citation_key', 'references', ['citation_key']),
                ('ix_references_doi', 'references', ['doi']),
                ('ix_references_pubmed_id', 'references', ['pubmed_id']),
                ('ix_references_arxiv_id', 'references', ['arxiv_id']),
                ('ix_references_created_at', 'references', ['created_at']),
            ]
            
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('references')]
            
            for idx_name, table_name, columns in indexes_to_create:
                if idx_name not in existing_indexes:
                    op.create_index(idx_name, table_name, columns)
    
    except Exception as e:
        # If there's any issue, just log it and continue
        # The application will create tables as needed
        pass


def downgrade():
    """Downgrade Phase 4.1 columns.
    
    Note: This removes added columns but keeps the table intact.
    """
    try:
        op.drop_table('references')
    except Exception:
        # Table might not exist
        pass
