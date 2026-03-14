import pytest
import uuid
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import git
from app.workers.tasks import _process_repository, process_repository_task, process_webhook_task
from app.services.git_service import git_service

def test_process_webhook_task():
    process_webhook_task({"event": "push"})

@pytest.mark.asyncio
async def test_process_repository_invalid_uuid():
    await _process_repository("not-a-uuid", "http://test")

@pytest.mark.asyncio
@patch('app.workers.tasks.async_session_maker')
async def test_process_repository_not_found(mock_session_maker):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Mock async with async_session_maker() as db
    mock_session_maker.return_value.__aenter__.return_value = mock_db
    await _process_repository(str(uuid.uuid4()), "http://test")

@pytest.mark.asyncio
@patch('app.workers.tasks.async_session_maker')
@patch('app.workers.tasks.git_service')
async def test_process_repository_success(mock_git, mock_session_maker):
    mock_job = MagicMock()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_db
    
    mock_git.clone_repository.return_value = "/tmp/repo"
    mock_git.get_supported_files.return_value = ["file1.py", "file2.py"]
    
    await _process_repository(str(uuid.uuid4()), "http://test")
    assert mock_job.status == "completed"

@pytest.mark.asyncio
@patch('app.workers.tasks.async_session_maker')
@patch('app.workers.tasks.git_service')
async def test_process_repository_exception(mock_git, mock_session_maker):
    mock_job = MagicMock()
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_job
    mock_db.execute.return_value = mock_result
    mock_session_maker.return_value.__aenter__.return_value = mock_db
    
    mock_git.clone_repository.side_effect = Exception("Clone failed")
    
    await _process_repository(str(uuid.uuid4()), "http://test")
    assert mock_job.status == "failed"

def test_process_repository_task_wrapper():
    with patch('app.workers.tasks.asyncio.run') as mock_run:
        process_repository_task(str(uuid.uuid4()), "http://test")
        mock_run.assert_called_once()
        
def test_git_service_clone():
    with patch('git.Repo.clone_from') as mock_clone:
        with patch('tempfile.mkdtemp', return_value="/tmp/test"):
            repo_path = git_service.clone_repository("http://test")
            assert repo_path == "/tmp/test"
            mock_clone.assert_called_once()
            
def test_git_service_get_files():
    with patch('pathlib.Path.rglob') as mock_rglob:
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_file.suffix = ".py"
        mock_file.parts = ["main.py"]
        mock_file.relative_to.return_value = "main.py"
        mock_rglob.return_value = [mock_file]
        
        files = git_service.get_supported_files("/tmp/test")
        assert len(files) == 1
        assert files[0] == "main.py"
        
def test_git_service_cleanup():
    with patch('shutil.rmtree') as mock_rmtree:
        git_service.cleanup_repository("/tmp/test")
        mock_rmtree.assert_called_once_with("/tmp/test", ignore_errors=True)
