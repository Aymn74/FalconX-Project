# PharmIntel User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Data Import](#data-import)
3. [Module Guides](#module-guides)
4. [CLI Commands](#cli-commands)
5. [Web Dashboard](#web-dashboard)
6. [API Usage](#api-usage)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### System Requirements
- Python 3.10 or higher
- 4GB RAM minimum (8GB recommended)
- 1GB free disk space
- Modern web browser (for dashboard)

### Installation Steps

1. **Install Python Dependencies**
```bash
pip install -r pharmintel/requirements.txt
```

2. **Initialize Database**
```bash
pharmintel database init
```

3. **Import Your Data**
```bash
pharmintel import-data excel /path/to/pharmaceutical_data.xlsx
```

4. **Seed Sample Data** (Optional, for testing)
```bash
pharmintel import-data seed-hospitals
```

## Data Import

### Preparing Your Excel File

Your Excel file should contain the following columns:

#### Required Columns
- **Material**: Drug name (e.g., "Paracetamol 500mg Tablet")
- **Material Number**: Unique identifier (e.g., "100012345")

#### Recommended Columns
- **External Material Group**: Classification
- **NUPCO CODE**: NUPCO identification
- **NUPCO DESCRIPTION**: NUPCO description
- **Unit Of Use**: Dosage unit (e.g., "Tablet", "Vial")
- **Classification**: Drug class
- **Therapeutic Area**: Category (e.g., "Cardiology", "Oncology")
- **ATC level1-4**: ATC classifications
- **Restrictions**: Any restrictions on use

#### Optional Inventory Fields
- **Expiry Date**: Format: YYYY-MM-DD
- **Batch Number**: Batch identifier
- **Current Stock**: Numeric value
- **Reorder Point**: Numeric value
- **Cost Per Unit**: Numeric value (currency)

### Import Process

```bash
# Basic import
pharmintel import-data excel data.xlsx

# Import from specific sheet
pharmintel import-data excel data.xlsx --sheet "Formulary 2024"

# View import statistics
pharmintel database stats
```

## Module Guides

### 1. Gap Analysis

**Purpose**: Identify gaps in formulary coverage compared to WHO Essential Medicines List.

**CLI Usage:**
```bash
# Run gap analysis
pharmintel analyze gap

# Generate HTML report
pharmintel analyze gap --format html

# Generate specific report
pharmintel report generate gap --format json
```

**Python API:**
```python
from pharmintel.core.database import get_database
from pharmintel.analyzers.gap_analysis import FormularyGapAnalyzer

db = get_database()
with db.get_session() as session:
    analyzer = FormularyGapAnalyzer(session)

    # Get comprehensive report
    report = analyzer.generate_comprehensive_report()

    # Get coverage for specific area
    coverage = analyzer.analyze_therapeutic_area_coverage("Cardiology")
    print(f"Cardiology coverage: {coverage['coverage_percentage']}%")
```

**Key Outputs:**
- Coverage percentage by therapeutic area
- Missing WHO essential medicines
- Gap severity classifications
- Priority recommendations

### 2. Pharmacogenomics Analysis

**Purpose**: Identify drug-gene interactions and provide personalized medicine insights.

**CLI Usage:**
```bash
# Analyze specific drug
pharmintel analyze pharmacogenomics --drug-id 123

# Analyze entire formulary
pharmintel analyze pharmacogenomics
```

**Python API:**
```python
from pharmintel.analyzers.pharmacogenomics import PharmacogenomicsAnalyzer

with db.get_session() as session:
    analyzer = PharmacogenomicsAnalyzer(session)

    # Get report for specific drug
    report = analyzer.generate_pgx_report(drug_id=123)

    # Get high-priority interactions
    high_priority = analyzer.get_high_priority_interactions()

    # Arab population considerations
    arab_considerations = analyzer.get_arab_population_considerations()
```

**Key Outputs:**
- Drug-gene interaction details
- Clinical significance levels
- Population-specific recommendations
- Dosing adjustments

### 3. Expiry Tracking

**Purpose**: Monitor drug expiry dates and prevent wastage.

**CLI Usage:**
```bash
# Check expiry alerts (next 90 days)
pharmintel analyze expiry --days 90

# Generate expiry report
pharmintel report generate expiry --format html
```

**Python API:**
```python
from pharmintel.tracking.expiry_tracker import ExpiryTracker

with db.get_session() as session:
    tracker = ExpiryTracker(session)

    # Get critical alerts (< 30 days)
    critical = tracker.get_critical_alerts()

    # Get all expiring batches
    all_alerts = tracker.get_all_expiring_batches(days_threshold=90)

    # Get wastage statistics
    stats = tracker.calculate_wastage_statistics()

    # Update batch priorities
    tracker.update_batch_priorities()
```

**Key Features:**
- 30/60/90-day alert thresholds
- Wastage risk assessment
- Near-expiry prioritization
- Lending opportunity identification

### 4. Inventory Management

**Purpose**: Optimize inventory levels with AI-based predictions.

**CLI Usage:**
```bash
# Check inventory status
pharmintel analyze inventory

# Generate inventory report
pharmintel report generate inventory
```

**Python API:**
```python
from pharmintel.tracking.inventory import InventoryManager

with db.get_session() as session:
    manager = InventoryManager(session)

    # Analyze usage patterns
    prediction = manager.analyze_usage_patterns(drug_id=123, lookback_days=90)

    # Check stock levels
    alerts = manager.check_stock_levels()

    # Optimize reorder points
    manager.optimize_reorder_points()

    # Identify slow-moving items
    slow_moving = manager.identify_slow_moving_items()
```

**Key Features:**
- Usage velocity calculation
- Reorder point optimization
- Stock-out predictions
- Slow-moving item identification

### 5. Inter-Hospital Lending

**Purpose**: Track and manage drug lending between hospitals.

**CLI Usage:**
```bash
# View lending activity
pharmintel analyze lending

# Generate lending report
pharmintel report generate lending
```

**Python API:**
```python
from pharmintel.tracking.lending_tracker import LendingTracker

with db.get_session() as session:
    tracker = LendingTracker(session)

    # Create lending request
    transaction = tracker.create_lending_request(
        drug_id=123,
        from_hospital_id=1,
        to_hospital_id=2,
        quantity=100,
        request_reason="Emergency supply needed",
        requested_by="Dr. Smith"
    )

    # Approve request
    tracker.approve_lending_request(
        transaction_id=transaction.id,
        approved_by="Pharmacy Director"
    )

    # Check hospital balance
    balance = tracker.calculate_hospital_balance(hospital_id=1)

    # Get overdue returns
    overdue = tracker.get_overdue_returns()
```

**Key Features:**
- Request workflow management
- Reciprocal balance tracking
- Overdue return monitoring
- Network visibility

### 6. Non-Formulary Evaluation

**Purpose**: Analyze non-formulary drug usage and identify promotion candidates.

**CLI Usage:**
```bash
# Analyze non-formulary usage (180 days)
pharmintel analyze non-formulary --days 180

# Generate report
pharmintel report generate non-formulary
```

**Python API:**
```python
from pharmintel.analyzers.non_formulary import NonFormularyEvaluator

with db.get_session() as session:
    evaluator = NonFormularyEvaluator(session)

    # Analyze specific drug
    analysis = evaluator.analyze_non_formulary_usage(drug_id=123, lookback_days=180)

    # Get promotion candidates
    candidates = evaluator.identify_promotion_candidates(min_score=5.0)

    # Calculate cost impact
    cost_impact = evaluator.calculate_cost_impact()

    # Track exceptions
    exceptions = evaluator.track_exception_requests()
```

**Key Features:**
- Usage frequency analysis
- Promotion scoring (0-10)
- Cost impact assessment
- Exception request tracking

## CLI Commands

### Database Commands
```bash
# Initialize database
pharmintel database init

# Reset database (WARNING: deletes all data)
pharmintel database init --reset

# Show statistics
pharmintel database stats
```

### Import Commands
```bash
# Import from Excel
pharmintel import-data excel /path/to/file.xlsx

# Import from specific sheet
pharmintel import-data excel file.xlsx --sheet "Sheet1"

# Seed sample hospitals
pharmintel import-data seed-hospitals
```

### Analysis Commands
```bash
# Gap analysis
pharmintel analyze gap --format html

# Expiry tracking
pharmintel analyze expiry --days 90

# Inventory analysis
pharmintel analyze inventory

# Lending analysis
pharmintel analyze lending

# Non-formulary analysis
pharmintel analyze non-formulary --days 180

# Pharmacogenomics
pharmintel analyze pharmacogenomics

# Run all analyses
pharmintel analyze all --format html
```

### Server Commands
```bash
# Start API server
pharmintel server api --host 0.0.0.0 --port 8000 --reload

# Start web dashboard
pharmintel server dashboard --port 8501
```

### Report Commands
```bash
# Generate specific report
pharmintel report generate gap --format json
pharmintel report generate expiry --format html
pharmintel report generate inventory --format json
```

## Web Dashboard

### Accessing the Dashboard

```bash
# Start dashboard
streamlit run pharmintel/web/dashboard.py

# Or using CLI
pharmintel server dashboard
```

Access at: `http://localhost:8501`

### Dashboard Modules

1. **Overview**: System-wide summary and quick insights
2. **Gap Analysis**: Coverage heatmaps and gap identification
3. **Pharmacogenomics**: PGx interactions and recommendations
4. **Expiry Tracking**: Expiry alerts and wastage prevention
5. **Inventory Management**: Stock levels and predictions
6. **Lending Tracker**: Inter-hospital lending activity
7. **Non-Formulary**: Usage analysis and promotion candidates
8. **Enhancement Recommendations**: Optimization opportunities

### Dashboard Features
- Interactive charts and visualizations
- Filterable data tables
- Real-time data updates
- Export capabilities
- Responsive design

## API Usage

### Starting the API Server

```bash
# Production
uvicorn pharmintel.api.rest_api:app --host 0.0.0.0 --port 8000

# Development (with auto-reload)
uvicorn pharmintel.api.rest_api:app --reload
```

### API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Example API Calls

**Get All Drugs:**
```bash
curl http://localhost:8000/api/drugs?limit=10
```

**Gap Analysis:**
```bash
curl http://localhost:8000/api/gap-analysis
```

**Expiry Alerts:**
```bash
curl http://localhost:8000/api/expiry/critical
```

**Create Lending Request:**
```bash
curl -X POST http://localhost:8000/api/lending/request \
  -H "Content-Type: application/json" \
  -d '{
    "drug_id": 123,
    "from_hospital_id": 1,
    "to_hospital_id": 2,
    "quantity": 100,
    "request_reason": "Emergency",
    "requested_by": "Dr. Smith"
  }'
```

## Troubleshooting

### Common Issues

**Issue: Database not found**
```bash
# Solution: Initialize database
pharmintel database init
```

**Issue: Import fails with validation errors**
```bash
# Check Excel file format
# Ensure required columns are present: Material, Material Number
# Check for duplicate Material Numbers
```

**Issue: No data in reports**
```bash
# Verify data was imported
pharmintel database stats

# Check if specific module has data
pharmintel analyze gap
```

**Issue: API server won't start**
```bash
# Check if port is already in use
lsof -i :8000

# Try different port
pharmintel server api --port 8001
```

**Issue: Dashboard shows errors**
```bash
# Reinstall dependencies
pip install --upgrade -r pharmintel/requirements.txt

# Check database connection
pharmintel database stats
```

### Getting Help

```bash
# General help
pharmintel --help

# Command-specific help
pharmintel analyze --help
pharmintel database --help
```

### Logging

Logs are saved to: `pharmintel/pharmintel.log`

View logs:
```bash
tail -f pharmintel/pharmintel.log
```

## Best Practices

1. **Regular Backups**: Backup database regularly
   ```bash
   cp pharmintel/database/pharmintel.db pharmintel_backup_$(date +%Y%m%d).db
   ```

2. **Data Updates**: Import updated data regularly to maintain accuracy

3. **Review Recommendations**: Always review system recommendations with clinical expertise

4. **Monitor Alerts**: Check critical alerts daily

5. **Update Reorder Points**: Optimize reorder points monthly based on usage patterns

---

For additional support, refer to the main [README](../README.md) or open an issue on GitHub.
