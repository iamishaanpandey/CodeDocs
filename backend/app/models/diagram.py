import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship

from app.core.database import Base

class Diagram(Base):
    __tablename__ = "diagrams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    diagram_type: Mapped[str] = mapped_column(String, nullable=False)
    entry_point_path: Mapped[str | None] = mapped_column(String, nullable=True)
    mermaid_markup: Mapped[str] = mapped_column(Text, nullable=False)
    render_attempts: Mapped[int] = mapped_column(Integer, default=1)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    rendered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository: Mapped["Repository"] = relationship("Repository", back_populates="diagrams")
