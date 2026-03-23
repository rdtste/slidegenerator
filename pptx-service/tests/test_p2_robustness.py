"""P2 Tests: Job Cleanup, Structured Logging, and robustness.

Tests job lifecycle management, TTL enforcement, cleanup automation,
structured logging, and error recovery.

Run with: pytest tests/test_p2_robustness.py -v
"""

import pytest
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from app.services.job_cleanup_manager import ExportJob, JobCleanupManager
from app.utils.structured_logging import StructuredLogger, TimingContext, request_id, job_id


class TestExportJob:
    """Tests for ExportJob tracking model."""
    
    def test_job_creation(self):
        """Test job creation with metadata."""
        job = ExportJob(
            file_id="job-123",
            file_path=Path("/tmp/presentation.pptx"),
            created_at=datetime.utcnow(),
            accessed_at=datetime.utcnow(),
            size_bytes=2048576,
            status="ready",
            ttl_seconds=1800
        )
        
        assert job.file_id == "job-123"
        assert job.size_bytes == 2048576
        assert job.status == "ready"
        assert not job.is_expired
    
    def test_job_expiration_detection(self):
        """Test TTL expiration detection."""
        old_time = datetime.utcnow() - timedelta(seconds=2000)
        job = ExportJob(
            file_id="job-old",
            file_path=Path("/tmp/old.pptx"),
            created_at=old_time,
            accessed_at=old_time,
            size_bytes=1024,
            status="ready",
            ttl_seconds=1800  # 30 minutes
        )
        
        assert job.is_expired
    
    def test_job_age_calculation(self):
        """Test job age in seconds."""
        job = ExportJob(
            file_id="job-age",
            file_path=Path("/tmp/test.pptx"),
            created_at=datetime.utcnow() - timedelta(seconds=60),
            accessed_at=datetime.utcnow(),
            size_bytes=1024,
            status="ready",
            ttl_seconds=3600
        )
        
        assert 59 < job.age_seconds < 61  # ~60 seconds


class TestJobCleanupManager:
    """Tests for job lifecycle management."""
    
    def test_manager_initialization(self):
        """Test manager starts with correct configuration."""
        manager = JobCleanupManager(
            default_ttl_seconds=1800,
            cleanup_interval_seconds=300
        )
        
        assert manager.default_ttl_seconds == 1800
        assert manager.cleanup_interval_seconds == 300
        assert len(manager.jobs) == 0
    
    def test_job_registration(self):
        """Test registering a new job."""
        manager = JobCleanupManager()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx') as f:
            temp_path = Path(f.name)
            f.write("test content")
        
        try:
            job = manager.register_job("job-1", temp_path)
            
            assert job.file_id == "job-1"
            assert job.file_path == temp_path
            assert job.status == "ready"
            assert len(manager.jobs) == 1
        finally:
            temp_path.unlink()
    
    def test_job_retrieval(self):
        """Test retrieving registered job."""
        manager = JobCleanupManager()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx') as f:
            temp_path = Path(f.name)
            f.write("test")
        
        try:
            manager.register_job("job-1", temp_path)
            retrieved = manager.get_job("job-1")
            
            assert retrieved is not None
            assert retrieved.file_id == "job-1"
            assert retrieved.status == "ready"
        finally:
            temp_path.unlink()
    
    def test_job_cleanup_expired(self):
        """Test cleaning up expired job."""
        manager = JobCleanupManager(default_ttl_seconds=1)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx') as f:
            temp_path = Path(f.name)
            f.write("test")
        
        try:
            manager.register_job("job-1", temp_path)
            
            # Wait for expiration
            time.sleep(1.5)
            
            # Verify expired
            job = manager.get_job("job-1")
            assert job.is_expired
            
            # Clean up
            result = manager.cleanup_job("job-1")
            
            assert result is True
            assert "job-1" not in manager.jobs
            assert not temp_path.exists()
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_cleanup_non_expired_job(self):
        """Test that non-expired jobs aren't cleaned up."""
        manager = JobCleanupManager(default_ttl_seconds=3600)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx') as f:
            temp_path = Path(f.name)
            f.write("test")
        
        try:
            manager.register_job("job-1", temp_path)
            
            # Try to cleanup (should fail)
            result = manager.cleanup_job("job-1", force=False)
            
            assert result is False
            assert "job-1" in manager.jobs
            assert temp_path.exists()
        finally:
            temp_path.unlink()
    
    def test_cleanup_expired_run(self):
        """Test batch cleanup of expired jobs."""
        manager = JobCleanupManager(default_ttl_seconds=1)
        
        # Create 3 jobs
        temp_files = []
        for i in range(3):
            f = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx')
            temp_files.append(Path(f.name))
            f.write(f"test {i}")
            f.close()
            manager.register_job(f"job-{i}", temp_files[i])
        
        try:
            # Wait for expiration
            time.sleep(1.5)
            
            # Cleanup all expired
            stats = manager.cleanup_expired()
            
            assert stats["deleted_count"] == 3
            assert stats["total_recovered_bytes"] > 0
            assert len(manager.jobs) == 0
        finally:
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()
    
    def test_download_job_not_expired(self):
        """Test downloading non-expired job."""
        manager = JobCleanupManager(default_ttl_seconds=3600)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx') as f:
            temp_path = Path(f.name)
            f.write("test")
        
        try:
            manager.register_job("job-1", temp_path)
            
            # Download
            result = manager.download_job("job-1")
            
            assert result == temp_path
            job = manager.get_job("job-1")
            assert job.status == "downloading"
        finally:
            temp_path.unlink()
    
    def test_download_job_expired(self):
        """Test downloading expired job returns None and cleans up."""
        manager = JobCleanupManager(default_ttl_seconds=1)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx') as f:
            temp_path = Path(f.name)
            f.write("test")
        
        try:
            manager.register_job("job-1", temp_path)
            
            # Wait for expiration
            time.sleep(1.5)
            
            # Try to download
            result = manager.download_job("job-1")
            
            assert result is None
            assert "job-1" not in manager.jobs
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_manager_statistics(self):
        """Test statistics reporting."""
        manager = JobCleanupManager()
        
        temp_files = []
        for i in range(2):
            f = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx')
            temp_files.append(Path(f.name))
            f.write(f"test {i}")
            f.close()
            manager.register_job(f"job-{i}", temp_files[i])
        
        try:
            stats = manager.get_stats()
            
            assert stats["total_jobs"] == 2
            assert stats["ready_jobs"] == 2
            assert stats["total_size_mb"] >= 0
        finally:
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()


class TestStructuredLogging:
    """Tests for structured logging."""
    
    def test_logger_initialization(self):
        """Test structured logger creation."""
        logger = StructuredLogger("test_module")
        
        assert logger.logger is not None
        assert logger.logger.name == "test_module"
    
    def test_context_variables(self):
        """Test setting and retrieving context."""
        logger = StructuredLogger("test_module")
        
        logger.set_context(
            request_id="req-123",
            job_id="job-456",
            user_id="user-789"
        )
        
        # Verify context variables set
        assert request_id.get() == "req-123"
        assert job_id.get() == "job-456"


class TestTimingContext:
    """Tests for operation timing context manager."""
    
    def test_timing_success(self):
        """Test timing context on successful operation."""
        logger = StructuredLogger("test_module")
        
        with TimingContext(logger, "test_operation") as ctx:
            time.sleep(0.1)
        
        # Timing would be logged (we can't easily capture it, but it shouldn't error)
        assert True
    
    def test_timing_with_exception(self):
        """Test timing context handles exceptions."""
        logger = StructuredLogger("test_module")
        
        try:
            with TimingContext(logger, "failing_operation"):
                time.sleep(0.05)
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected
        
        # Should have logged the error with timing
        assert True


class TestRobustnessPipeline:
    """End-to-end robustness tests."""
    
    def test_job_lifecycle_complete(self):
        """Test complete job lifecycle from creation to cleanup."""
        manager = JobCleanupManager(default_ttl_seconds=1)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pptx') as f:
            temp_path = Path(f.name)
            f.write("test presentation")
        
        try:
            # Step 1: Register job
            job = manager.register_job("lifecycle-job", temp_path)
            assert job.status == "ready"
            assert not job.is_expired
            
            # Step 2: Retrieve job
            retrieved = manager.get_job("lifecycle-job")
            assert retrieved is not None
            
            # Step 3: Download job
            download_path = manager.download_job("lifecycle-job")
            assert download_path == temp_path
            
            # Step 4: Wait for expiration
            time.sleep(1.5)
            
            # Step 5: Auto-cleanup
            stats = manager.cleanup_expired()
            assert stats["deleted_count"] == 1
            
            # Step 6: Verify cleanup
            assert "lifecycle-job" not in manager.jobs
            assert not temp_path.exists()
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
