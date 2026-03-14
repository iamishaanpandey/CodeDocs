import asyncio
import sys
import uuid
import logging
from datetime import datetime
from celery import shared_task
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import SyncSessionLocal
from app.models.scan_job import ScanJob
from app.models.repository import Repository

logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def _update_job(db: Session, job_id: str, status: str, percent: int, message: str):
    """Synchronous job status update using psycopg2."""
    job = db.get(ScanJob, uuid.UUID(job_id))
    if job:
        job.status = status
        job.progress_percent = percent
        job.progress_message = message
        db.commit()

def _generate_diagrams(db: Session, repo_id: uuid.UUID):
    from app.models.diagram import Diagram
    from app.models.documentation import Documentation
    
    docs = db.execute(select(Documentation).where(Documentation.repository_id == repo_id)).scalars().all()
    if not docs:
        return
        
    files = {}
    for d in docs:
        if d.function_name:
            if d.file_path not in files:
                files[d.file_path] = []
            files[d.file_path].append(d)
            
    arch_lines = ["graph TD"]
    for path in files.keys():
        node_id = path.replace("/", "_").replace(".", "_").replace("-", "_")
        arch_lines.append(f'  {node_id}["{path}"]')
        
    class_lines = ["classDiagram"]
    for path, funcs in files.items():
        node_id = path.replace("/", "_").replace(".", "_").replace("-", "_")
        class_lines.append(f"  class {node_id} {{")
        for f in funcs:
            class_lines.append(f"    +{f.function_name}()")
        class_lines.append("  }")
        
    flow_lines = ["flowchart TD"]
    sorted_funcs = sorted([d for d in docs if d.function_name], key=lambda x: x.cyclomatic_complexity or 0, reverse=True)[:20]
    for i, func in enumerate(sorted_funcs):
        node_id = f"node_{i}"
        flow_lines.append(f'  {node_id}["{func.function_name}"]')
        if i > 0:
            prev_id = f"node_{i-1}"
            flow_lines.append(f"  {prev_id} --> {node_id}")
            
    diagrams_data = [
        {"type": "architecture", "markup": "\n".join(arch_lines)},
        {"type": "class_diagram", "markup": "\n".join(class_lines)},
        {"type": "flowchart", "markup": "\n".join(flow_lines)},
    ]
    
    for d_data in diagrams_data:
        diagram = db.execute(
            select(Diagram).where(Diagram.repository_id == repo_id, Diagram.diagram_type == d_data["type"])
        ).scalar_one_or_none()
        
        if diagram:
            diagram.mermaid_markup = d_data["markup"]
        else:
            diagram = Diagram(repository_id=repo_id, diagram_type=d_data["type"], mermaid_markup=d_data["markup"])
            db.add(diagram)
    db.commit()

@shared_task(name="process_repository")
def process_repository_task(job_id: str, repo_id: str):
    """Fully synchronous Celery task. Uses psycopg2, zero asyncpg."""
    # SyncSessionLocal uses psycopg2, NOT asyncpg
    with SyncSessionLocal() as db:
        try:
            # Immediately mark as running
            job = db.get(ScanJob, uuid.UUID(job_id))
            if not job:
                raise ValueError(f"ScanJob {job_id} not found in database")
            job.status = "running"
            job.started_at = datetime.utcnow()
            db.commit()
            logger.info(f"Job {job_id} started")

            repo = db.get(Repository, uuid.UUID(repo_id))
            if not repo:
                raise ValueError(f"Repository {repo_id} not found")

            # 1. Clone the repository
            _update_job(db, job_id, "running", 10, "Cloning repository...")
            from app.services.git_service import git_service
            try:
                repo_dir = git_service.clone_repository(str(repo.id), repo.github_repo_url)
            except Exception as e:
                raise ValueError(f"Failed to clone repository: {e}")

            try:
                # 2. Find supported files
                _update_job(db, job_id, "running", 20, "Scanning files...")
                files = git_service.get_supported_files(repo_dir)
                total_files = len(files)
                
                job = db.get(ScanJob, uuid.UUID(job_id))
                job.total_files = total_files
                db.commit()

                if total_files == 0:
                    _update_job(db, job_id, "completed", 100, "No supported files found.")
                    return

                # 3. Parse and process files
                from app.services.ingestion.ast_parser import parse_python_file, parse_general_file
                from app.services.ingestion.complexity_scorer import score_code_complexity
                from app.models.documentation import Documentation
                import os

                processed_count = 0
                for file_path in files:
                    _update_job(db, job_id, "running", int(20 + (processed_count / total_files) * 70), f"Processing {file_path}")
                    
                    full_path = os.path.join(repo_dir, file_path)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except Exception:
                        processed_count += 1
                        continue

                    if file_path.endswith('.py'):
                        parse_result = parse_python_file(content, file_path)
                        complexities = score_code_complexity(content)
                    else:
                        parse_result = parse_general_file(content, file_path)
                        complexities = {}

                    for func in parse_result.get("functions", []):
                        name = func["name"]
                        # Check if it already exists
                        existing = db.execute(
                            select(Documentation).where(
                                Documentation.repository_id == repo.id,
                                Documentation.file_path == file_path,
                                Documentation.function_name == name
                            )
                        ).scalar_one_or_none()

                        if not existing:
                            doc = Documentation(
                                repository_id=repo.id,
                                file_path=file_path,
                                function_name=name,
                                lines_of_code=func.get("end_lineno", func["lineno"]) - func["lineno"] + 1,
                                cyclomatic_complexity=complexities.get(name),
                                docstring=func.get("docstring")
                            )
                            db.add(doc)
                    
                    db.commit()
                    processed_count += 1
                    
                    job = db.get(ScanJob, uuid.UUID(job_id))
                    job.processed_files = processed_count
                    db.commit()

            finally:
                # 4. Keep repo cloned for file-tree and auth mapping APIs
                # git_service.cleanup_repository(repo_dir)
                pass

            # Generate diagrams
            _generate_diagrams(db, repo.id)
            
            # Mark complete
            _update_job(db, job_id, "completed", 100, "Scan completed successfully.")
            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            try:
                job = db.get(ScanJob, uuid.UUID(job_id))
                job.status = "failed"
                job.error_message = str(e)[:500]
                job.completed_at = datetime.utcnow()
                db.commit()
            except Exception:
                pass
            raise
