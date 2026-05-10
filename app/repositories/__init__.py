"""Repository layer — data access abstraction.

Each repository provides typed CRUD operations for a single aggregate root.
Services call repositories, never the database directly.
"""

from app.repositories.base import BaseRepository
