"""Batch operations service for Phase 4.2."""

from datetime import timedelta
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import csv
import io
from sqlalchemy import or_
from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher.batch_operations import (
    BatchJob,
    BatchJobResult,
    BatchJobLog,
    BatchJobStatus,
    ExportFormat,
)
from app.models.researcher.plugins import Plugin
from app.services.plugin_manager import PluginManager
from app.services.plugin_permissions import PluginPermissionService
from app.models.researcher.plugin_permissions import AccessLevel


class BatchOperationService:
    """Service for managing batch operations and parallel plugin execution."""

    MAX_PARALLEL_JOBS = 5  # Max concurrent plugin executions
    BATCH_TIMEOUT_SECONDS = 3600  # 1 hour timeout per batch

    @staticmethod
    def _status_value(status) -> str:
        return status.value if hasattr(status, "value") else str(status)

    @staticmethod
    def create_batch_job(
        user_id: int,
        name: str,
        plugins_list: List[int],
        source_data_type: str = "extraction_result",
        source_data_id: int = None,
        description: str = None,
        data_filters: dict = None,
        estimated_duration: int = 300,
    ) -> Tuple[bool, str, Optional[BatchJob]]:
        """Create a new batch job.

        Args:
            user_id: User creating the job
            name: Job name
            plugins_list: List of plugin IDs to execute
            source_data_type: Type of source data
            source_data_id: ID of source data
            description: Optional description
            data_filters: Optional filtering criteria
            estimated_duration: Estimated runtime in seconds

        Returns:
            Tuple of (success, message, job_object)
        """
        try:
            # Create job
            plugins_config = [{"plugin_id": pid, "options": {}} for pid in plugins_list]

            job = BatchJob(
                user_id=user_id,
                name=name,
                description=description,
                plugins_config=plugins_config,
                data_filters=data_filters or {},
                source_data_type=source_data_type,
                source_data_id=source_data_id,
                estimated_duration=estimated_duration,
            )

            db.session.add(job)
            db.session.commit()

            return True, "Batch job created", job

        except Exception as e:
            db.session.rollback()
            return False, f"Error creating batch job: {str(e)}", None

    @staticmethod
    def start_batch_job(
        job_id: int, user_id: int, total_records: int = 0
    ) -> Tuple[bool, str]:
        """Start executing a batch job.

        Args:
            job_id: Batch job ID
            user_id: User starting the job
            total_records: Total records to process

        Returns:
            Tuple of (success, message)
        """
        try:
            job = db.session.get(BatchJob, job_id)
            if not job:
                return False, "Batch job not found"

            if job.user_id != user_id:
                return False, "Unauthorized"

            if (
                BatchOperationService._status_value(job.status)
                != BatchJobStatus.pending.value
            ):
                return False, f"Job is already {job.status}"

            job.total_records = total_records
            job.mark_started()

            return True, "Batch job started"

        except Exception as e:
            return False, f"Error starting batch job: {str(e)}"

    @staticmethod
    def pause_batch_job(job_id: int, user_id: int) -> Tuple[bool, str]:
        """Pause a running batch job."""
        try:
            job = db.session.get(BatchJob, job_id)
            if not job:
                return False, "Batch job not found"

            if job.user_id != user_id:
                return False, "Unauthorized"

            if (
                BatchOperationService._status_value(job.status)
                != BatchJobStatus.running.value
            ):
                return False, f"Cannot pause job with status {job.status}"

            job.mark_paused()
            return True, "Batch job paused"

        except Exception as e:
            return False, f"Error pausing batch job: {str(e)}"

    @staticmethod
    def cancel_batch_job(job_id: int, user_id: int) -> Tuple[bool, str]:
        """Cancel a batch job."""
        try:
            job = db.session.get(BatchJob, job_id)
            if not job:
                return False, "Batch job not found"

            if job.user_id != user_id:
                return False, "Unauthorized"

            if BatchOperationService._status_value(job.status) in [
                BatchJobStatus.completed.value,
                BatchJobStatus.failed.value,
                BatchJobStatus.cancelled.value,
            ]:
                return False, f"Cannot cancel {job.status} job"

            job.mark_cancelled()
            return True, "Batch job cancelled"

        except Exception as e:
            return False, f"Error cancelling batch job: {str(e)}"

    @staticmethod
    def get_batch_status(job_id: int) -> Dict:
        """Get status of a batch job."""
        try:
            job = db.session.get(BatchJob, job_id)
            if not job:
                return {"error": "Batch job not found"}

            status_data = job.to_dict()
            status_data["time_remaining"] = job.get_estimated_time_remaining()

            return status_data

        except Exception as e:
            return {"error": f"Error getting batch status: {str(e)}"}

    @staticmethod
    def execute_batch_parallel(
        job_id: int, records: List[Dict], max_workers: int = MAX_PARALLEL_JOBS
    ) -> Tuple[bool, str, List[Dict]]:
        """Execute plugins in parallel for batch records.

        Args:
            job_id: Batch job ID
            records: List of records to process
            max_workers: Max parallel workers

        Returns:
            Tuple of (success, message, results_list)
        """
        try:
            job = db.session.get(BatchJob, job_id)
            if not job:
                return False, "Batch job not found", []

            if BatchOperationService._status_value(job.status) not in [
                BatchJobStatus.pending.value,
                BatchJobStatus.running.value,
                BatchJobStatus.paused.value,
            ]:
                return False, f"Cannot execute job with status {job.status}", []

            job.mark_started()

            # Get plugins to execute
            plugins = []
            for config in job.plugins_config:
                plugin = db.session.get(Plugin, config["plugin_id"])
                if plugin:
                    plugins.append(plugin)

            if not plugins:
                return False, "No accessible plugins found", []

            results = []
            successful = 0
            failed = 0

            # Execute plugins in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}

                for idx, record in enumerate(records):
                    for plugin in plugins:
                        # Check permission before execution
                        access = PluginPermissionService.check_user_access(
                            job.user_id, plugin.id, "execute"
                        )

                        if not access[0]:
                            # Skip this plugin for this user
                            continue

                        future = executor.submit(
                            BatchOperationService._execute_plugin_on_record,
                            job_id=job_id,
                            record_index=idx,
                            record=record,
                            plugin=plugin,
                            user_id=job.user_id,
                        )
                        futures[future] = (idx, plugin.id)

                # Collect results as they complete
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)

                        if result["success"]:
                            successful += 1
                        else:
                            failed += 1

                        # Update progress
                        job.update_progress(
                            processed=len(results), successful=successful, failed=failed
                        )

                    except Exception as e:
                        record_idx, plugin_id = futures[future]
                        failed += 1

                        error_result = {
                            "record_index": record_idx,
                            "plugin_id": plugin_id,
                            "success": False,
                            "error_message": str(e),
                        }
                        results.append(error_result)

                        job.update_progress(
                            processed=len(results), successful=successful, failed=failed
                        )

            job.mark_completed()
            return True, "Batch execution completed", results

        except Exception as e:
            job = db.session.get(BatchJob, job_id)
            if job:
                job.mark_failed("Batch execution failed", {"error": str(e)})

            return False, f"Error executing batch: {str(e)}", []

    @staticmethod
    def _execute_plugin_on_record(
        job_id: int, record_index: int, record: Dict, plugin: "Plugin", user_id: int
    ) -> Dict:
        """Execute a single plugin on a single record.

        Internal method called by thread pool.

        Note: Plugin execution requires the async hook system.
        The PluginManager.execute_hook() method is async and must be
        called via asyncio.run() from this synchronous context.
        """
        start_time = utcnow_naive()
        try:
            from app.services.plugin_base import HookContext

            plugin_manager = PluginManager()
            context = HookContext(data=record, user_id=user_id)

            import asyncio

            results = asyncio.run(
                plugin_manager.execute_hook(
                    hook_point=plugin.hook_point or "process_record",
                    context=context,
                )
            )

            result = results[0] if results else None
            execution_time = (utcnow_naive() - start_time).total_seconds() * 1000

            # Store result
            job_result = BatchJobResult(
                batch_job_id=job_id,
                record_index=record_index,
                plugin_id=plugin.id,
                plugin_name=plugin.name,
                success=True,
                result_data=result.get("data") if result else None,
                execution_time_ms=execution_time,
            )
            db.session.add(job_result)
            db.session.commit()

            return {
                "record_index": record_index,
                "plugin_id": plugin.id,
                "plugin_name": plugin.name,
                "success": True,
                "execution_time_ms": execution_time,
                "result": result,
            }

        except Exception as e:
            execution_time = (utcnow_naive() - start_time).total_seconds() * 1000

            # Store error result
            job_result = BatchJobResult(
                batch_job_id=job_id,
                record_index=record_index,
                plugin_id=plugin.id,
                plugin_name=plugin.name,
                success=False,
                error_message=str(e),
                execution_time_ms=execution_time,
            )
            db.session.add(job_result)
            db.session.commit()

            return {
                "record_index": record_index,
                "plugin_id": plugin.id,
                "plugin_name": plugin.name,
                "success": False,
                "error_message": str(e),
                "execution_time_ms": execution_time,
            }

    @staticmethod
    def export_to_csv(job_id: int) -> Tuple[bool, str, Optional[str]]:
        """Export batch results to CSV.

        Returns:
            Tuple of (success, message, csv_content)
        """
        try:
            job = db.session.get(BatchJob, job_id)
            if not job:
                return False, "Batch job not found", None

            results = BatchJobResult.query.filter(
                BatchJobResult.batch_job_id == job_id
            ).all()

            if not results:
                return False, "No results to export", None

            # Create CSV
            output = io.StringIO()
            fieldnames = [
                "record_index",
                "plugin_id",
                "plugin_name",
                "success",
                "error_message",
                "execution_time_ms",
            ]

            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                writer.writerow(
                    {
                        "record_index": result.record_index,
                        "plugin_id": result.plugin_id,
                        "plugin_name": result.plugin_name,
                        "success": result.success,
                        "error_message": result.error_message or "",
                        "execution_time_ms": result.execution_time_ms or 0,
                    }
                )

            csv_content = output.getvalue()
            output.close()

            # Update job with export info
            job.export_format = "csv"
            job.export_file_size = len(csv_content.encode("utf-8"))
            db.session.commit()

            return True, "CSV export generated", csv_content

        except Exception as e:
            return False, f"Error exporting to CSV: {str(e)}", None

    @staticmethod
    def export_to_json(job_id: int) -> Tuple[bool, str, Optional[str]]:
        """Export batch results to JSON.

        Returns:
            Tuple of (success, message, json_content)
        """
        try:
            job = db.session.get(BatchJob, job_id)
            if not job:
                return False, "Batch job not found", None

            results = BatchJobResult.query.filter(
                BatchJobResult.batch_job_id == job_id
            ).all()

            export_data = {
                "batch_job": job.to_dict(),
                "results": [r.to_dict() for r in results],
                "summary": {
                    "total_records": job.total_records,
                    "processed": job.processed_records,
                    "successful": job.successful_records,
                    "failed": job.failed_records,
                },
            }

            json_content = json.dumps(export_data, indent=2, default=str)

            # Update job with export info
            job.export_format = "json"
            job.export_file_size = len(json_content.encode("utf-8"))
            db.session.commit()

            return True, "JSON export generated", json_content

        except Exception as e:
            return False, f"Error exporting to JSON: {str(e)}", None

    @staticmethod
    def get_batch_results(
        job_id: int, limit: int = 100, offset: int = 0, filter_success: bool = None
    ) -> Tuple[bool, str, List[Dict]]:
        """Get results from a batch job.

        Args:
            job_id: Batch job ID
            limit: Max results to return
            offset: Pagination offset
            filter_success: Filter to successful (True) or failed (False) results

        Returns:
            Tuple of (success, message, results_list)
        """
        try:
            query = BatchJobResult.query.filter(BatchJobResult.batch_job_id == job_id)

            if filter_success is not None:
                query = query.filter(BatchJobResult.success == filter_success)

            total = query.count()

            results = (
                query.order_by(BatchJobResult.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            return (
                True,
                f"Retrieved {len(results)} of {total} results",
                [r.to_dict() for r in results],
            )

        except Exception as e:
            return False, f"Error retrieving results: {str(e)}", []

    @staticmethod
    def get_batch_logs(
        job_id: int, level: str = None, limit: int = 100, offset: int = 0
    ) -> Tuple[bool, str, List[Dict]]:
        """Get logs from a batch job.

        Args:
            job_id: Batch job ID
            level: Filter by log level (info, warning, error, debug)
            limit: Max logs to return
            offset: Pagination offset

        Returns:
            Tuple of (success, message, logs_list)
        """
        try:
            query = BatchJobLog.query.filter(BatchJobLog.batch_job_id == job_id)

            if level:
                query = query.filter(BatchJobLog.level == level)

            total = query.count()

            logs = (
                query.order_by(BatchJobLog.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            return (
                True,
                f"Retrieved {len(logs)} of {total} logs",
                [log.to_dict() for log in logs],
            )

        except Exception as e:
            return False, f"Error retrieving logs: {str(e)}", []

    @staticmethod
    def add_batch_log(
        job_id: int,
        level: str,
        message: str,
        record_index: int = None,
        plugin_id: int = None,
    ) -> Tuple[bool, str]:
        """Add a log entry to a batch job.

        Args:
            job_id: Batch job ID
            level: Log level (info, warning, error, debug)
            message: Log message
            record_index: Optional record index
            plugin_id: Optional plugin ID

        Returns:
            Tuple of (success, message)
        """
        try:
            plugin_name = None
            if plugin_id:
                plugin = db.session.get(Plugin, plugin_id)
                plugin_name = plugin.name if plugin else None

            log = BatchJobLog(
                batch_job_id=job_id,
                level=level,
                message=message,
                record_index=record_index,
                plugin_id=plugin_id,
                plugin_name=plugin_name,
            )

            db.session.add(log)
            db.session.commit()

            return True, "Log entry added"

        except Exception as e:
            db.session.rollback()
            return False, f"Error adding log: {str(e)}"

    @staticmethod
    def cleanup_old_jobs(days: int = 30) -> Tuple[bool, str, int]:
        """Clean up completed batch jobs older than N days.

        Args:
            days: Delete jobs older than N days

        Returns:
            Tuple of (success, message, deleted_count)
        """
        try:
            cutoff = utcnow_naive() - timedelta(days=days)

            # Find old jobs
            old_jobs = BatchJob.query.filter(
                BatchJob.status.in_(
                    [
                        BatchJobStatus.completed,
                        BatchJobStatus.cancelled,
                        BatchJobStatus.failed,
                    ]
                ),
                or_(
                    BatchJob.completed_at < cutoff,
                    (BatchJob.completed_at.is_(None) & (BatchJob.created_at < cutoff)),
                ),
            ).all()

            deleted_count = len(old_jobs)

            for job in old_jobs:
                # Delete related results and logs
                BatchJobResult.query.filter(
                    BatchJobResult.batch_job_id == job.id
                ).delete()
                BatchJobLog.query.filter(BatchJobLog.batch_job_id == job.id).delete()
                db.session.delete(job)

            db.session.commit()

            return True, f"Cleaned up {deleted_count} old jobs", deleted_count

        except Exception as e:
            db.session.rollback()
            return False, f"Error cleaning up jobs: {str(e)}", 0
