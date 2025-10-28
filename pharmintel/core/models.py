"""
Data models for PharmIntel system using SQLAlchemy ORM.
"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    Boolean, Text, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class TherapeuticArea(enum.Enum):
    """Therapeutic area classifications."""
    IMMUNOLOGY = "Immunology"
    INTERNAL_MEDICINE = "Internal Medicine"
    GI_HORMONAL = "GI & Hormonal"
    CRITICAL_CARE = "Critical Care"
    NEUROPSYCHIATRY = "Neuropsychiatry"
    ONCOLOGY = "Oncology"
    CARDIOLOGY = "Cardiology"
    INFECTIOUS_DISEASE = "Infectious Disease"
    OTHER = "Other"


class FormularyStatus(enum.Enum):
    """Formulary status types."""
    FORMULARY = "Formulary"
    NON_FORMULARY = "Non-Formulary"
    RESTRICTED = "Restricted"
    CONDITIONAL = "Conditional"


class LendingStatus(enum.Enum):
    """Lending transaction status."""
    REQUESTED = "Requested"
    APPROVED = "Approved"
    IN_TRANSIT = "In Transit"
    DELIVERED = "Delivered"
    RETURNED = "Returned"
    CANCELLED = "Cancelled"


class Drug(Base):
    """Main drug/pharmaceutical product model."""
    __tablename__ = "drugs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Basic information
    material = Column(String(500), nullable=False)
    material_number = Column(String(100), unique=True, index=True)
    external_material_group = Column(String(200))

    # NUPCO information
    nupco_code = Column(String(100), index=True)
    nupco_description = Column(Text)
    has_nupco_code = Column(Boolean, default=False)
    is_newly_created_code = Column(Boolean, default=False)

    # Unit and classification
    unit_of_use = Column(String(50))
    classification = Column(String(200))

    # Therapeutic classification
    therapeutic_area = Column(SQLEnum(TherapeuticArea))
    atc_level_1 = Column(String(100))
    atc_level_2 = Column(String(100))
    atc_level_3 = Column(String(100))
    atc_level_4 = Column(String(100))
    atc_code = Column(String(20))

    # Formulary status
    formulary_status = Column(SQLEnum(FormularyStatus), default=FormularyStatus.FORMULARY)
    restrictions = Column(Text)

    # Inventory information
    current_stock_level = Column(Float, default=0)
    reorder_point = Column(Float)
    cost_per_unit = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    batches = relationship("DrugBatch", back_populates="drug", cascade="all, delete-orphan")
    lending_transactions = relationship("LendingTransaction", back_populates="drug")
    pgx_associations = relationship("PharmacogenomicAssociation", back_populates="drug")
    usage_records = relationship("DrugUsageRecord", back_populates="drug")

    def __repr__(self):
        return f"<Drug(material='{self.material}', nupco_code='{self.nupco_code}')>"


class DrugBatch(Base):
    """Drug batch/lot tracking with expiry information."""
    __tablename__ = "drug_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False)

    batch_number = Column(String(100), nullable=False, index=True)
    expiry_date = Column(Date, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    location = Column(String(200))

    # Status flags
    is_expired = Column(Boolean, default=False)
    is_near_expiry = Column(Boolean, default=False)
    priority_level = Column(Integer, default=0)  # Higher = more urgent to use

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    drug = relationship("Drug", back_populates="batches")

    def __repr__(self):
        return f"<DrugBatch(batch='{self.batch_number}', expiry='{self.expiry_date}')>"


class Hospital(Base):
    """Hospital/facility model for lending network."""
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    code = Column(String(50), unique=True, index=True)
    location = Column(String(200))
    contact_person = Column(String(200))
    contact_phone = Column(String(50))
    contact_email = Column(String(100))

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lending_from = relationship(
        "LendingTransaction",
        foreign_keys="LendingTransaction.from_hospital_id",
        back_populates="from_hospital"
    )
    lending_to = relationship(
        "LendingTransaction",
        foreign_keys="LendingTransaction.to_hospital_id",
        back_populates="to_hospital"
    )

    def __repr__(self):
        return f"<Hospital(name='{self.name}', code='{self.code}')>"


class LendingTransaction(Base):
    """Inter-hospital drug lending/borrowing transactions."""
    __tablename__ = "lending_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False)
    from_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False)
    to_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False)

    quantity = Column(Float, nullable=False)
    batch_number = Column(String(100))

    status = Column(SQLEnum(LendingStatus), default=LendingStatus.REQUESTED)

    request_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    approval_date = Column(DateTime)
    delivery_date = Column(DateTime)
    return_date = Column(DateTime)
    expected_return_date = Column(Date)

    # Justification and notes
    request_reason = Column(Text)
    approval_notes = Column(Text)
    delivery_notes = Column(Text)

    # Metadata
    requested_by = Column(String(200))
    approved_by = Column(String(200))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    drug = relationship("Drug", back_populates="lending_transactions")
    from_hospital = relationship(
        "Hospital",
        foreign_keys=[from_hospital_id],
        back_populates="lending_from"
    )
    to_hospital = relationship(
        "Hospital",
        foreign_keys=[to_hospital_id],
        back_populates="lending_to"
    )

    def __repr__(self):
        return f"<LendingTransaction(drug_id={self.drug_id}, status='{self.status.value}')>"


class PharmacogenomicAssociation(Base):
    """Pharmacogenomic drug-gene associations."""
    __tablename__ = "pharmacogenomic_associations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False)

    gene = Column(String(50), nullable=False, index=True)
    variant = Column(String(100))

    # Effect information
    effect_type = Column(String(100))  # metabolism, efficacy, toxicity, etc.
    effect_description = Column(Text)
    clinical_significance = Column(String(50))  # high, moderate, low

    # Population data
    affected_populations = Column(Text)  # JSON string of populations
    allele_frequency = Column(Float)

    # Recommendations
    recommendation = Column(Text)
    guideline_source = Column(String(200))  # CPIC, FDA, etc.

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    drug = relationship("Drug", back_populates="pgx_associations")

    def __repr__(self):
        return f"<PharmacogenomicAssociation(drug_id={self.drug_id}, gene='{self.gene}')>"


class DrugUsageRecord(Base):
    """Track drug usage for non-formulary analysis and inventory prediction."""
    __tablename__ = "drug_usage_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    drug_id = Column(Integer, ForeignKey("drugs.id"), nullable=False)

    usage_date = Column(Date, nullable=False, index=True)
    quantity_used = Column(Float, nullable=False)
    department = Column(String(200))
    indication = Column(String(500))

    # For non-formulary tracking
    is_non_formulary = Column(Boolean, default=False)
    justification = Column(Text)
    approved_by = Column(String(200))

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    drug = relationship("Drug", back_populates="usage_records")

    def __repr__(self):
        return f"<DrugUsageRecord(drug_id={self.drug_id}, date='{self.usage_date}')>"


class WHOEssentialMedicine(Base):
    """WHO Essential Medicines List for gap analysis."""
    __tablename__ = "who_essential_medicines"

    id = Column(Integer, primary_key=True, autoincrement=True)

    medicine_name = Column(String(500), nullable=False)
    category = Column(String(200))
    therapeutic_area = Column(String(200))

    is_in_formulary = Column(Boolean, default=False)
    mapped_drug_id = Column(Integer, ForeignKey("drugs.id"))

    # List metadata
    who_list_version = Column(String(20))
    added_year = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WHOEssentialMedicine(name='{self.medicine_name}')>"


class GapAnalysisResult(Base):
    """Store gap analysis findings."""
    __tablename__ = "gap_analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)

    analysis_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    therapeutic_area = Column(String(200))

    gap_type = Column(String(100))  # missing_class, coverage_low, etc.
    description = Column(Text)
    severity = Column(String(50))  # critical, high, medium, low

    recommendation = Column(Text)
    estimated_cost_impact = Column(Float)
    priority_score = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GapAnalysisResult(area='{self.therapeutic_area}', type='{self.gap_type}')>"


class EnhancementRecommendation(Base):
    """Store formulary enhancement recommendations."""
    __tablename__ = "enhancement_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    recommendation_type = Column(String(100))  # biosimilar, generic, consolidation, etc.
    current_drug_id = Column(Integer, ForeignKey("drugs.id"))
    suggested_drug_name = Column(String(500))

    rationale = Column(Text)
    estimated_savings = Column(Float)
    evidence_grade = Column(String(20))

    status = Column(String(50), default="pending")  # pending, approved, rejected, implemented
    reviewed_by = Column(String(200))
    review_date = Column(DateTime)
    review_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<EnhancementRecommendation(type='{self.recommendation_type}')>"
