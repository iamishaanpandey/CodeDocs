import os
import tempfile
import shutil
import git
from pathlib import Path

class GitService:
    @staticmethod
    def get_repo_path(repo_id: str) -> str:
        return os.path.join(tempfile.gettempdir(), f"codedocs_repo_{repo_id}")

    @staticmethod
    def clone_repository(repo_id: str, repo_url: str, branch: str = "main") -> str:
        """
        Clones a repository into a deterministic temporary directory based on repo_id.
        """
        target_dir = GitService.get_repo_path(repo_id)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)
            
        try:
            git.Repo.clone_from(repo_url, target_dir, branch=branch, depth=1)
            return target_dir
        except git.exc.GitCommandError as e:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise ValueError(f"Failed to clone repository: {e}")

    @staticmethod
    def get_supported_files(repo_path: str) -> list[str]:
        """
        Returns a list of relative paths for supported source files.
        """
        supported_extensions = {".py", ".js", ".ts", ".tsx", ".go", ".java", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".rs", ".rb", ".php", ".cs"}
        files = []
        path = Path(repo_path)
        for fp in path.rglob("*"):
            if fp.is_file() and fp.suffix in supported_extensions:
                # ignore hidden folders like .git
                if not any(part.startswith('.') for part in fp.parts):
                    files.append(str(fp.relative_to(path)))
        return files

    @staticmethod
    def cleanup_repository(repo_path: str):
        shutil.rmtree(repo_path, ignore_errors=True)

git_service = GitService()
