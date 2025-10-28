# PharmIntel - Pharmaceutical Intelligence System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**PharmIntel** is a comprehensive pharmaceutical intelligence system designed to optimize formulary management, track inventory, analyze pharmacogenomics, and improve medication safety across healthcare institutions.

## 🎯 Key Features

### 1️⃣ **Pharmacogenomics Analysis Engine**
- Drug-gene interaction checker with CYP450 metabolism pathways
- Therapeutic alternatives based on genetic profiles
- Population-specific medication recommendations (including Arab populations)
- Precision medicine compatibility scoring
- Adverse reaction risk profiling by genetic markers

### 2️⃣ **Formulary Gap Analysis**
- Comparison against WHO Essential Medicines List
- Therapeutic area coverage mapping
- Missing critical drug classes identification
- Competitive formulary benchmarking
- Disease prevalence vs. drug availability mismatch detector

### 3️⃣ **Enhancement Recommendation System**
- Cost-effectiveness analysis suggestions
- Biosimilar/generic substitution opportunities
- Duplicate therapeutic class consolidation
- Evidence-based formulary additions
- Therapeutic guideline compliance checker

### 4️⃣ **Expiry & Inventory Intelligence**
- Expiry date tracking & automated alerts (30/60/90 days)
- AI-based usage pattern prediction
- Near-expiry prioritization system
- Wastage reduction recommendations
- Reorder point optimization

### 5️⃣ **Inter-Hospital Lending Tracker**
- Lending request management workflow
- Hospital network inventory visibility
- Transfer history & comprehensive audit trail
- Reciprocal lending balance tracking
- Emergency supply coordination dashboard

### 6️⃣ **Non-Formulary Evaluator**
- Non-formulary usage frequency analysis
- Conversion candidates identification (non-formulary → formulary)
- Cost impact assessment of non-formulary approvals
- Clinical justification tracking
- Exception request workflow management

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pharmintel.git
cd pharmintel

# Install dependencies
pip install -r pharmintel/requirements.txt

# Or install in development mode
pip install -e .
```

### Database Setup

```bash
# Initialize database
pharmintel database init

# Import pharmaceutical data from Excel
pharmintel import-data excel /path/to/your/pharmaceutical_data.xlsx

# Seed sample hospital data (for lending network)
pharmintel import-data seed-hospitals
```

### Usage

#### Option 1: Command Line Interface (CLI)

```bash
# Run gap analysis
pharmintel analyze gap

# Check expiry alerts
pharmintel analyze expiry --days 90

# Run all analyses and generate executive summary
pharmintel analyze all --format html

# Start API server
pharmintel server api --host 0.0.0.0 --port 8000

# Start web dashboard
pharmintel server dashboard --port 8501
```

#### Option 2: Web Dashboard

```bash
# Launch Streamlit dashboard
streamlit run pharmintel/web/dashboard.py
```

Access dashboard at: `http://localhost:8501`

#### Option 3: REST API

```bash
# Start FastAPI server
uvicorn pharmintel.api.rest_api:app --host 0.0.0.0 --port 8000
```

API documentation available at: `http://localhost:8000/docs`

#### Option 4: Python API

```python
from pharmintel.core.database import get_database
from pharmintel.analyzers.gap_analysis import FormularyGapAnalyzer
from pharmintel.tracking.expiry_tracker import ExpiryTracker

# Initialize database
db = get_database()

# Run gap analysis
with db.get_session() as session:
    analyzer = FormularyGapAnalyzer(session)
    report = analyzer.generate_comprehensive_report()
    print(f"Found {report['summary']['total_gaps_identified']} gaps")

# Check expiry alerts
with db.get_session() as session:
    tracker = ExpiryTracker(session)
    critical_alerts = tracker.get_critical_alerts()
    print(f"Critical expiry alerts: {len(critical_alerts)}")
```

## 📂 Project Structure

```
pharmintel/
├── core/
│   ├── data_loader.py          # Excel data import & validation
│   ├── database.py              # Database management
│   └── models.py                # SQLAlchemy ORM models
├── analyzers/
│   ├── pharmacogenomics.py      # PGx analysis engine
│   ├── gap_analysis.py          # Formulary gap detection
│   ├── enhancement.py           # Enhancement recommendations
│   └── non_formulary.py         # Non-formulary evaluation
├── tracking/
│   ├── expiry_tracker.py        # Expiry management
│   ├── lending_tracker.py       # Inter-hospital lending
│   └── inventory.py             # Inventory intelligence
├── reports/
│   ├── generator.py             # Report generation engine
│   └── templates/               # Report templates
├── api/
│   └── rest_api.py              # FastAPI REST endpoints
├── cli/
│   └── commands.py              # CLI interface
├── web/
│   └── dashboard.py             # Streamlit dashboard
└── tests/                       # Unit tests
```

## 📊 Example Outputs

### Gap Analysis Report
```json
{
  "summary": {
    "total_gaps_identified": 15,
    "critical_gaps": 3,
    "high_priority_gaps": 8,
    "average_who_coverage": 78.5
  },
  "gaps_by_severity": {...},
  "recommendations": [
    "URGENT: Address 3 critical gap(s) immediately...",
    "Consider comprehensive review of: Critical Care, Immunology"
  ]
}
```

### Expiry Alerts
```
Critical Expiry Alerts (< 30 days):
- Infliximab Batch#2024-01 expires in 15 days (250 units)
- Rituximab Batch#2024-03 expires in 22 days (180 units)
```

### Pharmacogenomics Report
```
High-Priority PGx Interactions:
- Clopidogrel + CYP2C19 (Clinical Significance: HIGH)
  Recommendation: Consider prasugrel or ticagrelor for CYP2C19 poor metabolizers
```

## 🔌 API Endpoints

### Core Endpoints
- `GET /api/drugs` - List all drugs
- `GET /api/gap-analysis` - Formulary gap analysis
- `GET /api/pharmacogenomics/drug/{id}` - PGx report for drug
- `GET /api/expiry/alerts` - Expiry alerts
- `GET /api/inventory/alerts` - Stock level alerts
- `GET /api/lending/report` - Lending activity report
- `GET /api/non-formulary/report` - Non-formulary analysis

See full API documentation at `/docs` when server is running.

## 🧪 Testing

```bash
# Run unit tests
pytest pharmintel/tests/

# Run with coverage
pytest --cov=pharmintel pharmintel/tests/

# Run specific test module
pytest pharmintel/tests/test_gap_analysis.py
```

## 📋 Data Requirements

### Excel Input Format
The system expects pharmaceutical data in Excel format with the following columns:

**Required Fields:**
- `Material` - Drug name
- `Material Number` - Unique identifier
- `External Material Group` - Drug classification

**Optional Fields:**
- `NUPCO CODE` - NUPCO identification code
- `NUPCO DESCRIPTION` - NUPCO description
- `Unit Of Use` - Dosage unit
- `Classification` - Drug classification
- `Therapeutic Area` - Therapeutic category
- `ATC level1`, `ATC level2`, `ATC level3`, `ATC level4` - ATC classifications
- `Restrictions` - Usage restrictions

**Additional Tracking Fields:**
- `Expiry Date` - Batch expiry date
- `Batch Number` - Batch identifier
- `Current Stock` - Current stock level
- `Reorder Point` - Reorder threshold
- `Cost Per Unit` - Unit cost

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- PharmIntel Team

## 🙏 Acknowledgments

- WHO Essential Medicines List
- PharmGKB for pharmacogenomics data structures
- CPIC guidelines for pharmacogenomics recommendations
- Healthcare institutions providing feedback and requirements

## 📞 Support

For support, please:
- Open an issue on GitHub
- Email: support@pharmintel.example.com
- Documentation: [Full User Guide](docs/USER_GUIDE.md)

## 🗺️ Roadmap

### Version 2.0 (Planned)
- [ ] Integration with external pharmacogenomics databases (PharmGKB, CPIC)
- [ ] Real-time WHO EML API integration
- [ ] Machine learning for demand forecasting
- [ ] Multi-language support (Arabic, French, Spanish)
- [ ] Mobile application
- [ ] Advanced analytics dashboard with predictive models
- [ ] Integration with hospital EHR systems
- [ ] Blockchain-based lending audit trail

## ⚠️ Disclaimer

PharmIntel is a clinical decision support tool. All recommendations should be reviewed by qualified healthcare professionals before implementation. This system does not replace clinical judgment.

---

**Built with ❤️ for Healthcare**
