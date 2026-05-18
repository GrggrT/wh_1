from datetime import date, datetime
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(Text, nullable=False, server_default="ru")
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="PLN")
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="worker")
    crew_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("crews.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    # Phase 5.3: evening day-entry reminder. NULL = disabled.
    remind_hour_local: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="19",
    )
    day_reminder_last_sent: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Phase 6.3: onboarding wizard. NULL = wizard not yet completed.
    onboarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Phase 7.7: per-user timezone (IANA name, e.g. "Europe/Warsaw"). NULL =
    # fall back to the bot-wide setting.
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)

    sites: Mapped[list["Site"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="user")
    crew: Mapped["Crew | None"] = relationship(
        back_populates="members", foreign_keys=[crew_id],
    )


class Crew(Base):
    __tablename__ = "crews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    foreman_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    default_hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    members: Mapped[list["User"]] = relationship(
        back_populates="crew", foreign_keys="User.crew_id",
    )


class InviteCode(Base):
    __tablename__ = "invite_codes"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    crew_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("crews.id", ondelete="CASCADE"), nullable=False,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    polygon = mapped_column(Geography("POLYGON", srid=4326), nullable=True)
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="sites")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="site")


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    site_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sites.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_location = mapped_column(Geography("POINT", srid=4326), nullable=True)
    end_location = mapped_column(Geography("POINT", srid=4326), nullable=True)
    start_photo_file_id: Mapped[str | None] = mapped_column(Text)
    end_photo_file_id: Mapped[str | None] = mapped_column(Text)
    start_photo_path: Mapped[str | None] = mapped_column(Text)
    end_photo_path: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    work_type: Mapped[str | None] = mapped_column(Text)
    auto_closed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="shifts")
    site: Mapped["Site | None"] = relationship(back_populates="shifts")
    breaks: Mapped[list["Break"]] = relationship(
        back_populates="shift", cascade="all, delete-orphan",
    )


class Break(Base):
    __tablename__ = "breaks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shift_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    shift: Mapped["Shift"] = relationship(back_populates="breaks")


class DayEntry(Base):
    """Phase 5: simplified daily hours entry.

    One row per (user, day). Hours include any breaks (worker reports a single
    net number). `site_id` is set only when the "sites" feature toggle is ON.
    """

    __tablename__ = "day_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_day_entries_user_day"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    site_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sites.id", ondelete="SET NULL"),
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Advance(Base):
    """Phase 5.2: cash advance paid to a worker mid-period.

    Deducted from the worker's monthly salary computation.
    """

    __tablename__ = "advances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class SalaryPayment(Base):
    """Phase 6.6: salary payment ledger entry.

    `paid_on` = the date money was actually given to the worker.
    `period_year` + `period_month` = the accounting period the payment
    covers. These intentionally differ in the typical case (salary paid in
    May for April work), and tracking both separately is what makes the
    bookkeeping correct.
    """

    __tablename__ = "salary_payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class AppSettings(Base):
    """Phase 5.4: single-row global feature toggles.

    Single-tenant bot, so a single row (id=1) is sufficient. Defaults match
    the simplified Phase 5 product: just type hours per day, everything else
    optional.
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sites_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    crews_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    geofence_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    legacy_clock_inout_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class ShareToken(Base):
    """One-shot, time-bound token to transfer a user's data to another account."""

    __tablename__ = "share_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    source_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    redeemed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True,
    )


class CloudBackup(Base):
    """An XLSX backup snapshot uploaded to object storage, retrievable by key."""

    __tablename__ = "cloud_backups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
