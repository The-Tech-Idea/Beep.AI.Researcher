"""Phase 3 Knowledge Graph Service — builds citation graphs from project papers
and Semantic Scholar data, with support for vector and GraphRAG paths.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta

from app.core.time_utils import utcnow_naive
from typing import Any

import requests

from app.database import db
from app.models.researcher import Reference, ResearchProject

logger = logging.getLogger(__name__)

_SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"


class KnowledgeGraphCache(db.Model):
    """Cached knowledge graph per (user, project, date)."""

    __tablename__ = "knowledge_graph_cache"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    project_id = db.Column(db.Integer, nullable=True, index=True)
    nodes_json = db.Column(db.JSON)
    edges_json = db.Column(db.JSON)
    clusters_json = db.Column(db.JSON)
    built_at = db.Column(db.DateTime, default=utcnow_naive)
    expires_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="pending")  # pending|ready|failed

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "nodes": self.nodes_json or [],
            "edges": self.edges_json or [],
            "clusters": self.clusters_json or [],
            "built_at": self.built_at.isoformat() if self.built_at else None,
            "status": self.status,
        }


class KnowledgeGraphService:
    """Build and cache citation knowledge graphs."""

    MAX_NODES = 500

    def __init__(self, api_key: str | None = None, cache_repo=None):
        self.api_key = api_key
        self._session = requests.Session()
        if api_key:
            self._session.headers["x-api-key"] = api_key
        self._cache_repo = cache_repo

    @property
    def _repo(self):
        if self._cache_repo is None:
            from app.repositories.knowledge_graph_cache_repository import (
                KnowledgeGraphCacheRepository,
            )

            self._cache_repo = KnowledgeGraphCacheRepository()
        return self._cache_repo

    def build_graph(
        self,
        project: ResearchProject,
        user_id: int,
        *,
        use_cache: bool = True,
        max_nodes: int = MAX_NODES,
    ) -> dict[str, Any]:
        """Build a knowledge graph for a project's references.

        Returns {nodes: [...], edges: [...], clusters: [...]}
        """
        # Check cache (24h expiry)
        if use_cache:
            cached = self._repo.get_ready(user_id, project_id=project.id)
            if cached and cached.expires_at and cached.expires_at > utcnow_naive():
                return cached.to_dict()

        # Gather DOIs from project references
        refs = Reference.query.filter_by(project_id=project.id).all()
        dois = [r.doi for r in refs if r.doi]

        if not dois:
            return self._empty_graph()

        # Fetch citation edges from Semantic Scholar
        edges = self._fetch_citation_edges(dois[:max_nodes])

        # Build nodes
        nodes = self._build_nodes(refs[:max_nodes])

        # Try to get clusters
        clusters = []
        try:
            clusters = self._cluster_nodes(nodes, edges)
        except Exception as exc:
            logger.warning("KnowledgeGraphService: clustering failed: %s", exc)

        # Thin graph if too large
        if len(nodes) > max_nodes:
            nodes, edges = self._thin_graph(nodes, edges, max_nodes)

        # Cache result
        cache = KnowledgeGraphCache(
            user_id=user_id,
            project_id=project.id,
            nodes_json=nodes,
            edges_json=edges,
            clusters_json=clusters,
            status="ready",
            expires_at=utcnow_naive() + timedelta(days=1),
        )
        self._repo.add(cache)
        self._repo.commit()

        return {
            "nodes": nodes,
            "edges": edges,
            "clusters": clusters,
        }

    def expand_node(self, doi: str) -> dict[str, Any]:
        """Fetch 1-hop neighbours for a DOI."""
        try:
            resp = self._session.get(
                f"{_SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}",
                params={"fields": "title,authors,year,citations,references,abstract"},
                timeout=30,
            )
            if resp.status_code != 200:
                return {"error": f"API error: {resp.status_code}"}

            data = resp.json()
            nodes = []
            edges = []

            # Add the target node
            nodes.append(
                {
                    "id": f"doi:{data.get('externalIds', {}).get('DOI', '')}",
                    "title": data.get("title", ""),
                    "year": data.get("year"),
                    "authors": [a.get("name", "") for a in (data.get("authors") or [])],
                    "is_ghost": False,
                }
            )

            # Add citation neighbours
            for cite in (data.get("citations") or [])[:20]:
                cite_doi = cite.get("externalIds", {}).get("DOI", "")
                nodes.append(
                    {
                        "id": f"doi:{cite_doi}",
                        "title": cite.get("title", ""),
                        "year": cite.get("year"),
                        "is_ghost": True,
                    }
                )
                edges.append(
                    {
                        "source": f"doi:{data.get('externalIds', {}).get('DOI', '')}",
                        "target": f"doi:{cite_doi}",
                        "type": "cites",
                    }
                )

            return {"nodes": nodes, "edges": edges}

        except requests.RequestException as exc:
            return {"error": str(exc)}

    @staticmethod
    def _empty_graph():
        return {"nodes": [], "edges": [], "clusters": []}

    def _fetch_citation_edges(self, dois: list[str]) -> list[dict]:
        """Fetch citation relationships between DOIs from Semantic Scholar."""
        edges = []
        doi_set = {d.lower() for d in dois}

        for doi in dois[:50]:  # Rate limit: max 50 calls
            try:
                resp = self._session.get(
                    f"{_SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}/citations",
                    params={"fields": "externalIds", "limit": 50},
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json().get("data", [])
                for item in data:
                    cited_doi = item.get("externalIds", {}).get("DOI", "")
                    if cited_doi and cited_doi.lower() in doi_set:
                        edges.append(
                            {
                                "source": f"doi:{doi.lower()}",
                                "target": f"doi:{cited_doi.lower()}",
                                "type": "cites",
                            }
                        )
            except requests.RequestException:
                continue

        return edges

    @staticmethod
    def _build_nodes(refs: list[Reference]) -> list[dict]:
        """Build graph nodes from project references."""
        nodes = []
        for ref in refs:
            if not ref.doi:
                continue
            nodes.append(
                {
                    "id": f"doi:{ref.doi.lower()}",
                    "title": ref.title or "Untitled",
                    "year": ref.year,
                    "authors": ref.get_authors()[:3],
                    "source": ref.source,
                    "is_ghost": False,
                    "ref_id": ref.id,
                }
            )
        return nodes

    @staticmethod
    def _cluster_nodes(nodes: list[dict], edges: list[dict]) -> list[dict]:
        """Simple label-propagation clustering on the graph."""
        if not nodes:
            return []

        # Build adjacency
        adj = {}
        for node in nodes:
            adj[node["id"]] = set()

        for edge in edges:
            if edge["source"] in adj and edge["target"] in adj:
                adj[edge["source"]].add(edge["target"])
                adj[edge["target"]].add(edge["source"])

        # Simple connected-components clustering
        visited = set()
        clusters = []
        cluster_id = 0

        for node_id in adj:
            if node_id in visited:
                continue

            # BFS
            cluster_nodes = []
            queue = [node_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster_nodes.append(current)
                for neighbor in adj.get(current, []):
                    if neighbor not in visited:
                        queue.append(neighbor)

            if cluster_nodes:
                clusters.append(
                    {
                        "id": cluster_id,
                        "members": cluster_nodes,
                        "size": len(cluster_nodes),
                    }
                )
                cluster_id += 1

        return clusters

    @staticmethod
    def _thin_graph(
        nodes: list[dict], edges: list[dict], max_nodes: int
    ) -> tuple[list[dict], list[dict]]:
        """Reduce graph to max_nodes by keeping highest-degree nodes."""
        degree = {}
        for node in nodes:
            degree[node["id"]] = 0

        for edge in edges:
            if edge["source"] in degree:
                degree[edge["source"]] += 1
            if edge["target"] in degree:
                degree[edge["target"]] += 1

        sorted_nodes = sorted(degree.items(), key=lambda x: -x[1])[:max_nodes]
        keep_ids = {n[0] for n in sorted_nodes}

        kept_nodes = [n for n in nodes if n["id"] in keep_ids]
        kept_edges = [
            e for e in edges if e["source"] in keep_ids and e["target"] in keep_ids
        ]

        return kept_nodes, kept_edges
