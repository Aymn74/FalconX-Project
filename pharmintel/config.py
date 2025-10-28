"""
Configuration management for PharmIntel system.
"""
import os
from pathlib import Path
from typing import Optional

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports" / "output"
DB_DIR = BASE_DIR / "database"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)

# Database configuration
DATABASE_PATH = DB_DIR / "pharmintel.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# API configuration
API_HOST = os.getenv("PHARMINTEL_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PHARMINTEL_API_PORT", "8000"))
API_RELOAD = os.getenv("PHARMINTEL_API_RELOAD", "false").lower() == "true"

# Web dashboard configuration
WEB_HOST = os.getenv("PHARMINTEL_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("PHARMINTEL_WEB_PORT", "8501"))

# Expiry alert thresholds (days)
EXPIRY_ALERT_CRITICAL = 30
EXPIRY_ALERT_WARNING = 60
EXPIRY_ALERT_INFO = 90

# Inventory thresholds
LOW_STOCK_THRESHOLD = 10  # units
REORDER_MULTIPLIER = 1.5

# Logging configuration
LOG_LEVEL = os.getenv("PHARMINTEL_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = BASE_DIR / "pharmintel.log"

# External data sources
WHO_ESSENTIAL_MEDICINES_URL = "https://list.essentialmeds.org/"
PHARMACOGENOMICS_DB_PATH = DATA_DIR / "pgx_database.json"

# Report settings
REPORT_COMPANY_NAME = "PharmIntel"
REPORT_LOGO_PATH: Optional[Path] = None

# Analysis settings
MIN_USAGE_THRESHOLD = 5  # Minimum usage count for analysis
COST_OPTIMIZATION_THRESHOLD = 0.15  # 15% cost reduction minimum
