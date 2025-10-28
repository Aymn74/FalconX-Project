"""
FastAPI REST API for PharmIntel system.
"""
import logging
from typing import List, Optional
from datetime import date

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pharmintel.core.database import get_db_session, get_database
from pharmintel.core.models import Drug, Hospital
from pharmintel.analyzers.pharmacogenomics import PharmacogenomicsAnalyzer
from pharmintel.analyzers.gap_analysis import FormularyGapAnalyzer
from pharmintel.analyzers.enhancement import EnhancementAnalyzer
from pharmintel.analyzers.non_formulary import NonFormularyEvaluator
from pharmintel.tracking.expiry_tracker import ExpiryTracker
from pharmintel.tracking.inventory import InventoryManager
from pharmintel.tracking.lending_tracker import LendingTracker
from pharmintel.reports.generator import ReportGenerator

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PharmIntel API",
    description="Pharmaceutical Intelligence System API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class DrugResponse(BaseModel):
    id: int
    material: str
    material_number: str
    nupco_code: Optional[str]
    therapeutic_area: Optional[str]
    formulary_status: str
    current_stock_level: float

    class Config:
        from_attributes = True


class LendingRequestCreate(BaseModel):
    drug_id: int
    from_hospital_id: int
    to_hospital_id: int
    quantity: float
    request_reason: str
    requested_by: str


# Root endpoint
@app.get("/")
def read_root():
    """Root endpoint with API information."""
    return {
        "name": "PharmIntel API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "drugs": "/api/drugs",
            "gap_analysis": "/api/gap-analysis",
            "expiry": "/api/expiry",
            "inventory": "/api/inventory",
            "lending": "/api/lending",
            "non_formulary": "/api/non-formulary",
            "pgx": "/api/pharmacogenomics"
        }
    }


# Health check
@app.get("/health")
def health_check(db: Session = Depends(get_db_session)):
    """Health check endpoint."""
    try:
        # Test database connection
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")


# Drug endpoints
@app.get("/api/drugs", response_model=List[DrugResponse])
def get_drugs(
    skip: int = 0,
    limit: int = 100,
    therapeutic_area: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """Get list of drugs with optional filtering."""
    query = db.query(Drug)

    if therapeutic_area:
        query = query.filter(Drug.therapeutic_area == therapeutic_area)

    drugs = query.offset(skip).limit(limit).all()
    return drugs


@app.get("/api/drugs/{drug_id}", response_model=DrugResponse)
def get_drug(drug_id: int, db: Session = Depends(get_db_session)):
    """Get specific drug by ID."""
    drug = db.query(Drug).filter(Drug.id == drug_id).first()

    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")

    return drug


# Gap Analysis endpoints
@app.get("/api/gap-analysis")
def get_gap_analysis(db: Session = Depends(get_db_session)):
    """Get formulary gap analysis."""
    analyzer = FormularyGapAnalyzer(db)
    report = analyzer.generate_comprehensive_report()
    return report


@app.get("/api/gap-analysis/coverage")
def get_coverage_heatmap(db: Session = Depends(get_db_session)):
    """Get coverage heatmap data."""
    analyzer = FormularyGapAnalyzer(db)
    heatmap_data = analyzer.generate_coverage_heatmap_data()
    return heatmap_data


# Pharmacogenomics endpoints
@app.get("/api/pharmacogenomics/drug/{drug_id}")
def get_pgx_report(drug_id: int, db: Session = Depends(get_db_session)):
    """Get pharmacogenomics report for specific drug."""
    analyzer = PharmacogenomicsAnalyzer(db)
    try:
        report = analyzer.generate_pgx_report(drug_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/pharmacogenomics/high-priority")
def get_high_priority_pgx(
    therapeutic_area: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """Get high-priority pharmacogenomic interactions."""
    analyzer = PharmacogenomicsAnalyzer(db)
    interactions = analyzer.get_high_priority_interactions(therapeutic_area)
    return {"interactions": interactions}


# Expiry tracking endpoints
@app.get("/api/expiry/alerts")
def get_expiry_alerts(
    days_threshold: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db_session)
):
    """Get expiry alerts."""
    tracker = ExpiryTracker(db)
    alerts = tracker.get_all_expiring_batches(days_threshold)
    return {"alerts": [a.__dict__ for a in alerts]}


@app.get("/api/expiry/critical")
def get_critical_expiry_alerts(db: Session = Depends(get_db_session)):
    """Get critical expiry alerts (< 30 days)."""
    tracker = ExpiryTracker(db)
    alerts = tracker.get_critical_alerts()
    return {"critical_alerts": [a.__dict__ for a in alerts]}


@app.get("/api/expiry/report")
def get_expiry_report(db: Session = Depends(get_db_session)):
    """Get comprehensive expiry report."""
    tracker = ExpiryTracker(db)
    report = tracker.generate_expiry_report()
    return report


# Inventory endpoints
@app.get("/api/inventory/alerts")
def get_stock_alerts(db: Session = Depends(get_db_session)):
    """Get stock level alerts."""
    manager = InventoryManager(db)
    alerts = manager.check_stock_levels()
    return {"stock_alerts": [a.__dict__ for a in alerts]}


@app.get("/api/inventory/report")
def get_inventory_report(db: Session = Depends(get_db_session)):
    """Get comprehensive inventory report."""
    manager = InventoryManager(db)
    report = manager.generate_inventory_report()
    return report


@app.get("/api/inventory/slow-moving")
def get_slow_moving_items(
    threshold_days: int = Query(90, ge=30, le=365),
    db: Session = Depends(get_db_session)
):
    """Get slow-moving inventory items."""
    manager = InventoryManager(db)
    items = manager.identify_slow_moving_items(threshold_days)
    return {"slow_moving_items": items}


# Lending endpoints
@app.get("/api/lending/pending")
def get_pending_lending_requests(
    hospital_id: Optional[int] = None,
    db: Session = Depends(get_db_session)
):
    """Get pending lending requests."""
    tracker = LendingTracker(db)
    requests = tracker.get_pending_requests(hospital_id)
    return {"pending_requests": [r.id for r in requests], "count": len(requests)}


@app.post("/api/lending/request")
def create_lending_request(
    request: LendingRequestCreate,
    db: Session = Depends(get_db_session)
):
    """Create new lending request."""
    tracker = LendingTracker(db)

    try:
        transaction = tracker.create_lending_request(
            drug_id=request.drug_id,
            from_hospital_id=request.from_hospital_id,
            to_hospital_id=request.to_hospital_id,
            quantity=request.quantity,
            request_reason=request.request_reason,
            requested_by=request.requested_by
        )
        return {"transaction_id": transaction.id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/lending/report")
def get_lending_report(db: Session = Depends(get_db_session)):
    """Get lending activity report."""
    tracker = LendingTracker(db)
    report = tracker.generate_lending_report()
    return report


@app.get("/api/lending/balance/{hospital_id}")
def get_hospital_lending_balance(
    hospital_id: int,
    db: Session = Depends(get_db_session)
):
    """Get lending balance for specific hospital."""
    tracker = LendingTracker(db)

    try:
        balance = tracker.calculate_hospital_balance(hospital_id)
        return balance.__dict__
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Non-formulary endpoints
@app.get("/api/non-formulary/report")
def get_non_formulary_report(
    lookback_days: int = Query(180, ge=30, le=365),
    db: Session = Depends(get_db_session)
):
    """Get non-formulary analysis report."""
    evaluator = NonFormularyEvaluator(db)
    report = evaluator.generate_comprehensive_report(lookback_days)
    return report


@app.get("/api/non-formulary/candidates")
def get_promotion_candidates(
    min_score: float = Query(5.0, ge=0, le=10),
    db: Session = Depends(get_db_session)
):
    """Get drugs that are candidates for formulary promotion."""
    evaluator = NonFormularyEvaluator(db)
    candidates = evaluator.identify_promotion_candidates(min_score)
    return {"candidates": [c.__dict__ for c in candidates]}


# Enhancement recommendations endpoints
@app.get("/api/enhancement/recommendations")
def get_enhancement_recommendations(db: Session = Depends(get_db_session)):
    """Get formulary enhancement recommendations."""
    analyzer = EnhancementAnalyzer(db)
    recommendations = analyzer.generate_all_recommendations()

    # Convert dataclass objects to dicts
    result = {}
    for rec_type, rec_list in recommendations.items():
        result[rec_type] = [r.__dict__ for r in rec_list]

    return result


@app.get("/api/enhancement/summary")
def get_enhancement_summary(db: Session = Depends(get_db_session)):
    """Get enhancement recommendations summary."""
    analyzer = EnhancementAnalyzer(db)
    summary = analyzer.generate_summary_report()
    return summary


# Reports endpoints
@app.get("/api/reports/executive-summary")
def get_executive_summary(db: Session = Depends(get_db_session)):
    """Get executive summary combining all analyses."""
    # Gather all data
    gap_analyzer = FormularyGapAnalyzer(db)
    expiry_tracker = ExpiryTracker(db)
    inventory_manager = InventoryManager(db)
    lending_tracker = LendingTracker(db)
    non_formulary_evaluator = NonFormularyEvaluator(db)

    all_data = {
        "gap_analysis": gap_analyzer.generate_comprehensive_report(),
        "expiry": expiry_tracker.generate_expiry_report(),
        "inventory": inventory_manager.generate_inventory_report(),
        "lending": lending_tracker.generate_lending_report(),
        "non_formulary": non_formulary_evaluator.generate_comprehensive_report()
    }

    return all_data


# Database statistics
@app.get("/api/stats")
def get_database_stats(db: Session = Depends(get_db_session)):
    """Get database statistics."""
    database = get_database()
    table_info = database.get_table_info()

    return {
        "tables": table_info,
        "status": "healthy"
    }


if __name__ == "__main__":
    import uvicorn
    from pharmintel.config import API_HOST, API_PORT, API_RELOAD

    uvicorn.run(
        "pharmintel.api.rest_api:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_RELOAD
    )
