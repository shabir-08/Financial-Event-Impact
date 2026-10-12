from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, new_id, utcnow


class SavedAnalysis(Base):
    """An analysis run the user explicitly saved ("Save" in the UI), with the report snapshot taken at save time.

    One row per analysis run (saving again returns the existing row). ``saved_by`` is the display name sent by the
    frontend's local session; there is no server-side authentication, so it is a label, not an identity.
    """

    __tablename__ = "saved_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False,
                                                 unique=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_reports.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    saved_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
