"""Phase 3 Clustering Service — K-Means over embedding vectors with
automatic cluster selection via silhouette scoring.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ClusteringService:
    """Cluster documents using K-Means over embedding vectors."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def cluster(
        self,
        texts: list[str],
        *,
        min_clusters: int = 3,
        max_clusters: int = 15,
    ) -> dict[str, Any]:
        """Cluster texts using K-Means + silhouette scoring.

        Returns {clusters: [{id, members: [indices], label, top_terms}], labels: [cluster_id per text]}
        """
        if not texts:
            return {"clusters": [], "labels": []}

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.cluster import KMeans
            from sklearn.metrics import silhouette_score
        except ImportError:
            logger.warning(
                "ClusteringService: scikit-learn not installed, falling back to heuristic"
            )
            return self._heuristic_cluster(texts, min_clusters)

        # TF-IDF vectorization
        vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(texts)

        # Find optimal K via silhouette score
        best_k = min_clusters
        best_score = -1

        for k in range(min_clusters, min(max_clusters + 1, len(texts))):
            if k < 2:
                continue
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(tfidf_matrix)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(tfidf_matrix, labels)
            if score > best_score:
                best_score = score
                best_k = k

        # Final clustering
        km = KMeans(n_clusters=best_k, n_init=10, random_state=42)
        labels = km.fit_predict(tfidf_matrix)

        # Extract top terms per cluster
        feature_names = vectorizer.get_feature_names_out()
        clusters = []
        for i in range(best_k):
            members = [j for j, l in enumerate(labels) if l == i]
            center = km.cluster_centers_[i]
            top_indices = center.argsort()[-10:][::-1]
            top_terms = [feature_names[j] for j in top_indices]

            clusters.append(
                {
                    "id": i,
                    "members": members,
                    "label": ", ".join(top_terms[:3]),
                    "top_terms": top_terms,
                    "size": len(members),
                }
            )

        return {
            "clusters": clusters,
            "labels": labels.tolist(),
            "silhouette_score": round(best_score, 3),
            "k": best_k,
        }

    @staticmethod
    def _heuristic_cluster(texts: list[str], min_clusters: int) -> dict[str, Any]:
        """Fallback: simple length-based clustering."""
        n = max(min_clusters, min(len(texts) // 5, min_clusters * 2))
        chunk_size = max(1, len(texts) // n)
        clusters = []
        labels = [0] * len(texts)

        for i in range(0, len(texts), chunk_size):
            cluster_id = len(clusters)
            members = list(range(i, min(i + chunk_size, len(texts))))
            for j in members:
                labels[j] = cluster_id
            clusters.append(
                {
                    "id": cluster_id,
                    "members": members,
                    "label": f"Cluster {cluster_id + 1}",
                    "top_terms": [],
                    "size": len(members),
                }
            )

        return {"clusters": clusters, "labels": labels}
