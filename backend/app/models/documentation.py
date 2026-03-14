import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, UniqueConstraint, func
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base

class Documentation(Base):
    __tablename__ = "documentations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    function_name: Mapped[str] = mapped_column(String, nullable=False)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameter_descriptions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    return_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    big_o_estimate: Mapped[str | None] = mapped_column(String, nullable=True)
    cyclomatic_complexity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maintainability_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    lines_of_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    handles_pii: Mapped[bool] = mapped_column(Boolean, default=False)
    is_entry_point: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unprotected: Mapped[bool] = mapped_column(Boolean, default=False)
    decorators: Mapped[list] = mapped_column(JSON, default=list)
    callers: Mapped[list] = mapped_column(JSON, default=list)
    callees: Mapped[list] = mapped_column(JSON, default=list)
    external_services_called: Mapped[list] = mapped_column(JSON, default=list)
    db_models_queried: Mapped[list] = mapped_column(JSON, default=list)
    source_code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    git_blame_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    llm_model_used: Mapped[str | None] = mapped_column(String, nullable=True)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="documentations")

    __table_args__ = (
        UniqueConstraint('repository_id', 'file_path', 'function_name', name='uq_repo_file_func'),
    )
