import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base

class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    github_repo_url: Mapped[str] = mapped_column(String, nullable=False)
    github_repo_name: Mapped[str] = mapped_column(String, nullable=False)
    github_repo_owner: Mapped[str] = mapped_column(String, nullable=False)
    default_branch: Mapped[str] = mapped_column(String, default="main")
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_status: Mapped[str] = mapped_column(String, default="never_scanned")
    total_functions: Mapped[int] = mapped_column(Integer, default=0)
    total_endpoints: Mapped[int] = mapped_column(Integer, default=0)
    total_external_services: Mapped[int] = mapped_column(Integer, default=0)
    documentation_coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    security_score: Mapped[float] = mapped_column(Float, default=0.0)
    architectural_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    zombie_code_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_status: Mapped[str] = mapped_column(String, default="not_embedded")
    webhook_id: Mapped[str | None] = mapped_column(String, nullable=True)
    auto_scan_on_push: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="repositories")
    scan_jobs: Mapped[list["ScanJob"]] = relationship("ScanJob", back_populates="repository", cascade="all, delete-orphan")
    file_hashes: Mapped[list["FileHash"]] = relationship("FileHash", back_populates="repository", cascade="all, delete-orphan")
    documentations: Mapped[list["Documentation"]] = relationship("Documentation", back_populates="repository", cascade="all, delete-orphan")
    diagrams: Mapped[list["Diagram"]] = relationship("Diagram", back_populates="repository", cascade="all, delete-orphan")
    security_flags: Mapped[list["SecurityFlag"]] = relationship("SecurityFlag", back_populates="repository", cascade="all, delete-orphan")
    external_services: Mapped[list["ExternalService"]] = relationship("ExternalService", back_populates="repository", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'github_repo_url', name='uq_user_repo_url'),
    )
