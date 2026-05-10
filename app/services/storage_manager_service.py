"""Storage backend service — unified interface for local/S3/Azure/SMB storage
with health checks and consistency scanning.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.config_manager import config_manager


def _config_value(key: str, default: str = "") -> str:
    return config_manager.get(key, default)


class StorageManagerService:
    """Manage storage backends and perform health checks."""

    def __init__(self):
        self._backend = None

    def backend_name(self) -> str:
        return _config_value("storage.backend", "local")

    def health_check(self) -> dict[str, Any]:
        """Run health check against the active storage backend."""
        backend = self.backend_name()
        result: dict[str, Any] = {"backend": backend, "healthy": False, "details": {}}

        if backend == "local":
            result = self._check_local(result)
        elif backend == "s3":
            result = self._check_s3(result)
        elif backend == "azure":
            result = self._check_azure(result)
        elif backend == "smb":
            result = self._check_smb(result)
        else:
            result["details"]["error"] = f"Unknown backend: {backend}"

        return result

    def consistency_scan(self) -> dict[str, Any]:
        """Scan all stored objects and report inconsistencies."""
        backend = self.backend_name()
        result: dict[str, Any] = {
            "backend": backend,
            "total_documents": 0,
            "missing_files": 0,
            "orphaned_files": 0,
            "size_mismatch": 0,
            "details": [],
        }

        if backend != "local":
            result["details"].append(
                {"message": f"Consistency scan not implemented for {backend}"}
            )
            return result

        from app.models.researcher import ResearcherDocument, ResearchProject

        base_dir = _config_value("storage.local_path", "data/uploads")
        storage_path = Path(base_dir)

        if not storage_path.exists():
            result["details"].append(
                {"message": f"Storage directory does not exist: {storage_path}"}
            )
            return result

        # Check all documents
        documents = ResearcherDocument.query.all()
        result["total_documents"] = len(documents)

        for doc in documents:
            storage_key = doc.file_path or doc.filename
            file_path = storage_path / storage_key

            if not file_path.exists():
                result["missing_files"] += 1
                result["details"].append(
                    {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "issue": "file_missing",
                    }
                )
            elif doc.file_size and file_path.stat().st_size != doc.file_size:
                result["size_mismatch"] += 1
                result["details"].append(
                    {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        "expected_size": doc.file_size,
                        "actual_size": file_path.stat().st_size,
                        "issue": "size_mismatch",
                    }
                )

        # Check for orphaned files
        if storage_path.exists():
            stored_files = set()
            for f in storage_path.rglob("*"):
                if f.is_file():
                    stored_files.add(str(f.relative_to(storage_path)))

            doc_paths = {
                (d.file_path or d.filename)
                for d in ResearcherDocument.query.all()
                if d.file_path or d.filename
            }

            result["orphaned_files"] = len(stored_files - doc_paths)

        return result

    def _check_local(self, result: dict[str, Any]) -> dict[str, Any]:
        """Check local storage backend."""
        base_dir = _config_value("storage.local_path", "data/uploads")
        path = Path(base_dir)

        if not path.exists():
            result["details"]["path_exists"] = False
            result["details"]["error"] = f"Directory does not exist: {path}"
            return result

        result["details"]["path_exists"] = True
        result["details"]["path"] = str(path)
        result["details"]["writable"] = os.access(path, os.W_OK)
        result["details"]["total_size"] = sum(
            f.stat().st_size for f in path.rglob("*") if f.is_file()
        )

        result["healthy"] = True
        return result

    def _check_s3(self, result: dict[str, Any]) -> dict[str, Any]:
        """Check S3 storage backend."""
        try:
            import boto3

            bucket = _config_value("storage.s3_bucket", "")
            if not bucket:
                result["details"]["error"] = "S3 bucket not configured"
                return result

            client = boto3.client("s3")
            client.head_bucket(Bucket=bucket)
            result["details"]["bucket"] = bucket
            result["healthy"] = True
        except ImportError:
            result["details"]["error"] = "boto3 not installed"
        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    def _check_azure(self, result: dict[str, Any]) -> dict[str, Any]:
        """Check Azure Blob storage backend."""
        try:
            from azure.storage.blob import BlobServiceClient

            conn_str = _config_value("storage.azure_connection_string", "")
            if not conn_str:
                result["details"]["error"] = "Azure connection string not configured"
                return result

            client = BlobServiceClient.from_connection_string(conn_str)
            client.list_containers()
            result["healthy"] = True
        except ImportError:
            result["details"]["error"] = "azure-storage-blob not installed"
        except Exception as e:
            result["details"]["error"] = str(e)

        return result

    def _check_smb(self, result: dict[str, Any]) -> dict[str, Any]:
        """Check SMB storage backend."""
        share_path = _config_value("storage.smb_path", "")
        if not share_path:
            result["details"]["error"] = "SMB path not configured"
            return result

        path = Path(share_path)
        if path.exists():
            result["details"]["path"] = str(path)
            result["healthy"] = True
        else:
            result["details"]["error"] = f"SMB share not accessible: {share_path}"

        return result


storage_manager_service = StorageManagerService()
