import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, JSON, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base

class ExternalService(Base):
    __tablename__ = "external_services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    service_name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    service_type: Mapped[str] = mapped_column(String, default="unknown")
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    calling_functions: Mapped[list] = mapped_column(JSON, default=list)
    http_methods: Mapped[list] = mapped_column(JSON, default=list)
    is_internal_microservice: Mapped[bool] = mapped_column(Boolean, default=False)
    is_high_coupling: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository: Mapped["Repository"] = relationship("Repository", back_populates="external_services")
