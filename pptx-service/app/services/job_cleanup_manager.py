"""Export job manager with TTL cleanup (P2 robustness enhancement).

PPTX Skill requirement (Production Stability):
- Track export jobs with creation timestamps
- Automatic cleanup of old jobs (TTL: 30 minutes default)
- Prevent memory leaks from accumulated file references
- Configurable retention policies
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExportJob(BaseModel):
    """Export job metadata and tracking"""
    file_id: str
    file_path: Path
    created_at: datetime
    accessed_at: datetime
    size_bytes: int
    status: str  # "ready", "downloading", "deleted"
    ttl_seconds: int = 1800  # Default: 30 minutes
    
    @property
    def is_expired(self) -> bool:
        """Check if job exceeds TTL."""
        age_seconds = (datetime.utcnow() - self.created_at).total_seconds()
        return age_seconds > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get job age in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()


class JobCleanupManager:
    """Manages export job lifecycle and automatic cleanup.
    
    P2 Enhancement: Prevents memory leaks by tracking file references
    and automatically deleting expired export jobs after TTL.
    """

    def __init__(
        self,
        default_ttl_seconds: int = 1800,  # 30 minutes
        cleanup_interval_seconds: int = 300  # Check every 5 minutes
    ):
        self.jobs: dict[str, ExportJob] = {}
        self.default_ttl_seconds = default_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        
        logger.info(
            f"[Job Manager] Initialized with TTL={default_ttl_seconds}s, "
            f"cleanup interval={cleanup_interval_seconds}s"
        )
    
    def register_job(
        self,
        file_id: str,
        file_path: str | Path,
        ttl_seconds: Optional[int] = None
    ) -> ExportJob:
        """Register a new export job for tracking.
        
        Args:
            file_id: Unique job identifier
            file_path: Path to generated PPTX file
            ttl_seconds: Optional custom TTL (uses default if not provided)
            
        Returns:
            ExportJob with tracking metadata
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"[Job Manager] Registering job for non-existent file: {file_path}")
            size_bytes = 0
        else:
            size_bytes = file_path.stat().st_size
        
        job = ExportJob(
            file_id=file_id,
            file_path=file_path,
            created_at=datetime.utcnow(),
            accessed_at=datetime.utcnow(),
            size_bytes=size_bytes,
            status="ready",
            ttl_seconds=ttl_seconds or self.default_ttl_seconds
        )
        
        self.jobs[file_id] = job
        logger.info(
            f"[Job Manager] Registered job {file_id}: {file_path.name} "
            f"({size_bytes} bytes, TTL={job.ttl_seconds}s)"
        )
        
        return job
    
    def get_job(self, file_id: str) -> Optional[ExportJob]:
        """Get job metadata and update accessed_at.
        
        Args:
            file_id: Job identifier
            
        Returns:
            ExportJob or None if not found
        """
        job = self.jobs.get(file_id)
        
        if job:
            job.accessed_at = datetime.utcnow()
            
            if job.file_path.exists():
                job.status = "ready"
            else:
                job.status = "deleted"
                logger.warning(f"[Job Manager] File for job {file_id} no longer exists")
            
            logger.debug(f"[Job Manager] Retrieved job {file_id} (age={job.age_seconds:.0f}s)")
        
        return job
    
    def download_job(self, file_id: str) -> Optional[Path]:
        """Get job file path for download and clean up afterward.
        
        Args:
            file_id: Job identifier
            
        Returns:
            File path or None if job expired/not found
        """
        job = self.get_job(file_id)
        
        if not job:
            logger.warning(f"[Job Manager] Download attempt for non-existent job: {file_id}")
            return None
        
        if job.is_expired:
            logger.warning(f"[Job Manager] Download attempt for expired job: {file_id}")
            self.cleanup_job(file_id)
            return None
        
        job.status = "downloading"
        logger.info(f"[Job Manager] Download started for job {file_id}")
        
        return job.file_path
    
    def cleanup_job(self, file_id: str, force: bool = False) -> bool:
        """Delete job and associated file.
        
        Args:
            file_id: Job identifier
            force: Force deletion even if not expired
            
        Returns:
            True if deleted, False if not found
        """
        job = self.jobs.get(file_id)
        
        if not job:
            return False
        
        if not force and not job.is_expired:
            logger.debug(f"[Job Manager] Job {file_id} not yet expired, skipping cleanup")
            return False
        
        try:
            if job.file_path.exists():
                job.file_path.unlink()
                logger.info(f"[Job Manager] Deleted file for job {file_id}: {job.file_path.name}")
            
            del self.jobs[file_id]
            logger.info(f"[Job Manager] Cleaned up job {file_id} (age={job.age_seconds:.0f}s)")
            
            return True
        
        except Exception as e:
            logger.error(f"[Job Manager] Error cleaning up job {file_id}: {e}")
            return False
    
    def cleanup_expired(self) -> dict[str, int]:
        """Remove all expired jobs.
        
        Returns:
            Stats: {"deleted_count": N, "total_recovered_bytes": B}
        """
        expired_ids = [
            file_id for file_id, job in self.jobs.items()
            if job.is_expired
        ]
        
        deleted_count = 0
        recovered_bytes = 0
        
        for file_id in expired_ids:
            job = self.jobs[file_id]
            recovered_bytes += job.size_bytes
            
            if self.cleanup_job(file_id, force=True):
                deleted_count += 1
        
        if deleted_count > 0:
            logger.info(
                f"[Job Manager] Cleanup run: deleted {deleted_count} jobs, "
                f"recovered {recovered_bytes / 1024 / 1024:.1f} MB"
            )
        
        return {
            "deleted_count": deleted_count,
            "total_recovered_bytes": recovered_bytes
        }
    
    def start_cleanup_thread(self) -> None:
        """Start background cleanup thread."""
        if self._running:
            logger.warning("[Job Manager] Cleanup thread already running")
            return
        
        self._running = True
        
        def run_cleanup():
            logger.info(f"[Job Manager] Cleanup thread started (interval={self.cleanup_interval_seconds}s)")
            
            while self._running:
                try:
                    time.sleep(self.cleanup_interval_seconds)
                    
                    if self._running:
                        self.cleanup_expired()
                        self._log_stats()
                
                except Exception as e:
                    logger.error(f"[Job Manager] Cleanup thread error: {e}")
        
        self._cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
        self._cleanup_thread.start()
    
    def stop_cleanup_thread(self) -> None:
        """Stop background cleanup thread."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            logger.info("[Job Manager] Cleanup thread stopped")
    
    def _log_stats(self) -> None:
        """Log current job manager statistics."""
        total_size = sum(job.size_bytes for job in self.jobs.values())
        ready_count = len([j for j in self.jobs.values() if j.status == "ready"])
        
        logger.debug(
            f"[Job Manager] Stats: {len(self.jobs)} total jobs, "
            f"{ready_count} ready, {total_size / 1024 / 1024:.1f} MB total"
        )
    
    def get_stats(self) -> dict:
        """Get current manager statistics.
        
        Returns:
            {"total_jobs": N, "ready_jobs": N, "total_size_mb": F, "expired_count": N}
        """
        total_size = sum(job.size_bytes for job in self.jobs.values())
        ready_count = len([j for j in self.jobs.values() if j.status == "ready"])
        expired_count = len([j for j in self.jobs.values() if j.is_expired])
        
        return {
            "total_jobs": len(self.jobs),
            "ready_jobs": ready_count,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "expired_count": expired_count
        }
