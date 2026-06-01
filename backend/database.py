import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Support Railway's DATABASE_URL (Postgres) or fall back to SQLite in /tmp
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////tmp/estimate_comparison.db")

# Railway provides postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ComparisonJob(Base):
    __tablename__ = "comparison_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="queued")  # queued/extracting/matching/complete/failed
    carrier_pdf_path = Column(String)
    pa_pdf_path = Column(String)
    carrier_filename = Column(String)
    pa_filename = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)

    estimates = relationship("Estimate", back_populates="job", cascade="all, delete-orphan")
    line_matches = relationship("LineMatch", back_populates="job", cascade="all, delete-orphan")
    room_aggregates = relationship("RoomAggregate", back_populates="job", cascade="all, delete-orphan")
    category_aggregates = relationship("CategoryAggregate", back_populates="job", cascade="all, delete-orphan")
    financial_deltas = relationship("FinancialDelta", back_populates="job", cascade="all, delete-orphan")


class Estimate(Base):
    __tablename__ = "estimates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comparison_jobs.id"), nullable=False)
    source = Column(String)  # carrier/pa
    price_list_code = Column(String, nullable=True)
    estimator_name = Column(String, nullable=True)
    insured_name = Column(String, nullable=True)
    claim_number = Column(String, nullable=True)
    date_entered = Column(String, nullable=True)
    total_rcv = Column(Float, default=0.0)
    total_acv = Column(Float, default=0.0)
    overhead_pct = Column(Float, default=0.0)
    profit_pct = Column(Float, default=0.0)
    extraction_confidence = Column(Float, default=0.0)
    qa_passed = Column(Boolean, default=False)
    qa_issues = Column(Text, default="[]")  # JSON list

    job = relationship("ComparisonJob", back_populates="estimates")
    line_items = relationship("LineItem", back_populates="estimate", cascade="all, delete-orphan")


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    estimate_id = Column(String, ForeignKey("estimates.id"), nullable=False)
    room_name = Column(String, nullable=True)
    category_code = Column(String, nullable=True)
    selector_code = Column(String, nullable=True)
    activity_code = Column(String, nullable=True)
    description_raw = Column(Text)
    description_normalized = Column(Text)
    qty = Column(Float, default=0.0)
    unit = Column(String, nullable=True)
    unit_price = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    rcv = Column(Float, default=0.0)
    depreciation = Column(Float, default=0.0)
    acv = Column(Float, default=0.0)
    source_page = Column(Integer, default=0)
    is_misc = Column(Boolean, default=False)
    is_code_upgrade = Column(Boolean, default=False)
    extraction_confidence = Column(Float, default=1.0)

    estimate = relationship("Estimate", back_populates="line_items")


class LineMatch(Base):
    __tablename__ = "line_matches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comparison_jobs.id"), nullable=False)
    carrier_line_id = Column(String, ForeignKey("line_items.id"), nullable=True)
    pa_line_id = Column(String, ForeignKey("line_items.id"), nullable=True)
    match_type = Column(String)  # exact/fuzzy/semantic/unmatched
    match_state = Column(String)  # exact_match/qty_diff/price_diff/scope_diff/missing_from_carrier/only_in_carrier/unresolved
    confidence = Column(Float, default=0.0)
    qty_delta = Column(Float, default=0.0)
    unit_price_delta = Column(Float, default=0.0)
    rcv_delta = Column(Float, default=0.0)
    score_breakdown = Column(Text, default="{}")  # JSON
    human_reviewed = Column(Boolean, default=False)

    job = relationship("ComparisonJob", back_populates="line_matches")
    carrier_line = relationship("LineItem", foreign_keys=[carrier_line_id])
    pa_line = relationship("LineItem", foreign_keys=[pa_line_id])


class RoomAggregate(Base):
    __tablename__ = "room_aggregates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comparison_jobs.id"), nullable=False)
    room_name = Column(String)
    carrier_rcv = Column(Float, default=0.0)
    pa_rcv = Column(Float, default=0.0)
    rcv_delta = Column(Float, default=0.0)
    line_count_carrier = Column(Integer, default=0)
    line_count_pa = Column(Integer, default=0)
    missing_count = Column(Integer, default=0)

    job = relationship("ComparisonJob", back_populates="room_aggregates")


class CategoryAggregate(Base):
    __tablename__ = "category_aggregates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comparison_jobs.id"), nullable=False)
    category_code = Column(String)
    category_name = Column(String)
    carrier_rcv = Column(Float, default=0.0)
    pa_rcv = Column(Float, default=0.0)
    rcv_delta = Column(Float, default=0.0)
    pct_variance = Column(Float, default=0.0)
    missing_count = Column(Integer, default=0)

    job = relationship("ComparisonJob", back_populates="category_aggregates")


class FinancialDelta(Base):
    __tablename__ = "financial_deltas"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("comparison_jobs.id"), nullable=False)
    kind = Column(String)  # overhead/profit/material_tax/labor_tax/depreciation/deductible
    carrier_value = Column(Float, default=0.0)
    pa_value = Column(Float, default=0.0)
    delta = Column(Float, default=0.0)
    rationale = Column(Text, nullable=True)

    job = relationship("ComparisonJob", back_populates="financial_deltas")


def create_tables():
    Base.metadata.create_all(bind=engine)
