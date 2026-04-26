"""SQLAlchemy 2.0 declarative models for the device registry."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    sender_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eep: Mapped[str] = mapped_column(String(8), nullable=False)            # "A5-02-05"
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    paired_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Telegram(Base):
    __tablename__ = "telegrams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rorg: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hex: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    rssi_dbm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decoded_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_telegrams_sender_ts", "sender_id", "ts"),
    )


class GatewayMeta(Base):
    __tablename__ = "gateway_meta"

    k: Mapped[str] = mapped_column(String(64), primary_key=True)
    v: Mapped[str] = mapped_column(Text, nullable=False)
