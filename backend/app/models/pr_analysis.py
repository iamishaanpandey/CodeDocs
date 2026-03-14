import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base


class PRAnalysis(Base):
    """
    Persists the results of a Blast Radius PR analysis.
    One record per PR, updated if the PR is synchronized (new commits pushed).
    """
    __tablename__ = "pr_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String, nullable=True)
    diff_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Risk assessment results
    risk_level: Mapped[str] = mapped_column(String, default="LOW")          # LOW / MEDIUM / HIGH / CRITICAL
    affected_function_count: Mapped[int] = mapped_column(Integer, default=0)
    untested_function_count: Mapped[int] = mapped_column(Integer, default=0)
    affected_functions: Mapped[list] = mapped_column(JSON, default=list)    # [{name, file, complexity, risk}]

    # Generated artefacts
    mermaid_markup: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_comment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    comment_posted: Mapped[bool] = mapped_column(Boolean, default=False)

    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository: Mapped["Repository"] = relationship("Repository")
