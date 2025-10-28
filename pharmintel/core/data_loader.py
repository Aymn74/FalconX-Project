"""
Data loader for importing pharmaceutical data from Excel files.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime

from sqlalchemy.orm import Session
from pharmintel.core.models import (
    Drug, TherapeuticArea, FormularyStatus, DrugBatch, Hospital
)
from pharmintel.core.database import get_database

logger = logging.getLogger(__name__)


class DataLoader:
    """Load and validate pharmaceutical data from Excel files."""

    def __init__(self, excel_path: str):
        """
        Initialize data loader.

        Args:
            excel_path: Path to Excel file containing pharmaceutical data
        """
        self.excel_path = Path(excel_path)
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        self.df: Optional[pd.DataFrame] = None
        self.validation_errors: List[Dict] = []
        self.import_stats: Dict = {
            "total_rows": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "warnings": []
        }

    def load_excel(self, sheet_name: str = 0) -> pd.DataFrame:
        """
        Load data from Excel file.

        Args:
            sheet_name: Name or index of sheet to load

        Returns:
            DataFrame containing the data
        """
        logger.info(f"Loading Excel file: {self.excel_path}")

        try:
            self.df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
            self.import_stats["total_rows"] = len(self.df)
            logger.info(f"Loaded {len(self.df)} rows from Excel")
            return self.df
        except Exception as e:
            logger.error(f"Error loading Excel file: {e}")
            raise

    def validate_data(self) -> Tuple[bool, List[Dict]]:
        """
        Validate loaded data.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if self.df is None:
            return False, [{"error": "No data loaded. Call load_excel() first."}]

        errors = []

        # Check required columns
        required_columns = ["Material", "Material Number"]
        missing_columns = [col for col in required_columns if col not in self.df.columns]

        if missing_columns:
            errors.append({
                "type": "missing_columns",
                "columns": missing_columns
            })

        # Check for duplicate material numbers
        if "Material Number" in self.df.columns:
            duplicates = self.df[self.df["Material Number"].duplicated(keep=False)]
            if not duplicates.empty:
                errors.append({
                    "type": "duplicate_material_numbers",
                    "count": len(duplicates),
                    "examples": duplicates["Material Number"].head().tolist()
                })

        # Check data types and values
        for idx, row in self.df.iterrows():
            row_errors = []

            # Material validation
            if pd.isna(row.get("Material")):
                row_errors.append("Missing Material name")

            # Material Number validation
            if pd.isna(row.get("Material Number")):
                row_errors.append("Missing Material Number")

            if row_errors:
                errors.append({
                    "type": "row_validation",
                    "row": idx + 2,  # +2 for Excel row number (header + 0-index)
                    "errors": row_errors
                })

        self.validation_errors = errors
        is_valid = len(errors) == 0

        if is_valid:
            logger.info("Data validation passed")
        else:
            logger.warning(f"Data validation found {len(errors)} error(s)")

        return is_valid, errors

    def clean_data(self):
        """Clean and preprocess the loaded data."""
        if self.df is None:
            raise ValueError("No data loaded. Call load_excel() first.")

        logger.info("Cleaning data...")

        # Strip whitespace from string columns
        string_columns = self.df.select_dtypes(include=['object']).columns
        for col in string_columns:
            self.df[col] = self.df[col].str.strip() if self.df[col].dtype == 'object' else self.df[col]

        # Handle NUPCO codes
        if "NUPCO CODE" in self.df.columns:
            self.df["has_nupco_code"] = ~self.df["NUPCO CODE"].isna()
        else:
            self.df["has_nupco_code"] = False

        # Handle newly created codes (you may need to adjust this logic)
        # For now, assume items without NUPCO codes might be newly created
        self.df["is_newly_created_code"] = False

        logger.info("Data cleaning complete")

    def map_therapeutic_area(self, area_str: str) -> TherapeuticArea:
        """
        Map string therapeutic area to enum.

        Args:
            area_str: String representation of therapeutic area

        Returns:
            TherapeuticArea enum value
        """
        if pd.isna(area_str):
            return TherapeuticArea.OTHER

        area_mapping = {
            "immunology": TherapeuticArea.IMMUNOLOGY,
            "internal medicine": TherapeuticArea.INTERNAL_MEDICINE,
            "gi & hormonal": TherapeuticArea.GI_HORMONAL,
            "gi and hormonal": TherapeuticArea.GI_HORMONAL,
            "critical care": TherapeuticArea.CRITICAL_CARE,
            "neuropsychiatry": TherapeuticArea.NEUROPSYCHIATRY,
            "oncology": TherapeuticArea.ONCOLOGY,
            "cardiology": TherapeuticArea.CARDIOLOGY,
            "infectious disease": TherapeuticArea.INFECTIOUS_DISEASE,
        }

        area_lower = str(area_str).lower().strip()
        return area_mapping.get(area_lower, TherapeuticArea.OTHER)

    def map_formulary_status(self, classification: str, restrictions: str) -> FormularyStatus:
        """
        Determine formulary status from classification and restrictions.

        Args:
            classification: Drug classification
            restrictions: Restriction information

        Returns:
            FormularyStatus enum value
        """
        if pd.isna(classification):
            return FormularyStatus.FORMULARY

        classification_lower = str(classification).lower()

        if "non-formulary" in classification_lower:
            return FormularyStatus.NON_FORMULARY
        elif "restricted" in classification_lower or (not pd.isna(restrictions) and str(restrictions).strip()):
            return FormularyStatus.RESTRICTED
        elif "conditional" in classification_lower:
            return FormularyStatus.CONDITIONAL
        else:
            return FormularyStatus.FORMULARY

    def import_to_database(self, session: Session) -> Dict:
        """
        Import loaded data to database.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with import statistics
        """
        if self.df is None:
            raise ValueError("No data loaded. Call load_excel() first.")

        logger.info("Starting database import...")

        for idx, row in self.df.iterrows():
            try:
                # Create Drug object
                drug = Drug(
                    material=str(row.get("Material", "")),
                    material_number=str(row.get("Material Number", "")),
                    external_material_group=str(row.get("External Material Group", "")) if not pd.isna(row.get("External Material Group")) else None,
                    nupco_code=str(row.get("NUPCO CODE", "")) if not pd.isna(row.get("NUPCO CODE")) else None,
                    nupco_description=str(row.get("NUPCO DESCRIPTION", "")) if not pd.isna(row.get("NUPCO DESCRIPTION")) else None,
                    has_nupco_code=row.get("has_nupco_code", False),
                    is_newly_created_code=row.get("is_newly_created_code", False),
                    unit_of_use=str(row.get("Unit Of Use", "")) if not pd.isna(row.get("Unit Of Use")) else None,
                    classification=str(row.get("Classification", "")) if not pd.isna(row.get("Classification")) else None,
                    therapeutic_area=self.map_therapeutic_area(row.get("Therapeutic Area")),
                    atc_level_1=str(row.get("ATC level1", "")) if not pd.isna(row.get("ATC level1")) else None,
                    atc_level_2=str(row.get("ATC level2", "")) if not pd.isna(row.get("ATC level2")) else None,
                    atc_level_3=str(row.get("ATC level3", "")) if not pd.isna(row.get("ATC level3")) else None,
                    atc_level_4=str(row.get("ATC level4", "")) if not pd.isna(row.get("ATC level4")) else None,
                    atc_code=str(row.get("ATC Code", "")) if not pd.isna(row.get("ATC Code")) else None,
                    formulary_status=self.map_formulary_status(
                        row.get("Classification"),
                        row.get("Restrictions")
                    ),
                    restrictions=str(row.get("Restrictions", "")) if not pd.isna(row.get("Restrictions")) else None,
                    current_stock_level=float(row.get("Current Stock", 0)) if not pd.isna(row.get("Current Stock")) else 0,
                    reorder_point=float(row.get("Reorder Point")) if not pd.isna(row.get("Reorder Point")) else None,
                    cost_per_unit=float(row.get("Cost Per Unit")) if not pd.isna(row.get("Cost Per Unit")) else None
                )

                session.add(drug)
                self.import_stats["successful"] += 1

            except Exception as e:
                self.import_stats["failed"] += 1
                self.import_stats["warnings"].append({
                    "row": idx + 2,
                    "error": str(e)
                })
                logger.warning(f"Failed to import row {idx + 2}: {e}")

        try:
            session.commit()
            logger.info(f"Successfully imported {self.import_stats['successful']} records")
        except Exception as e:
            session.rollback()
            logger.error(f"Error committing to database: {e}")
            raise

        return self.import_stats

    def get_import_summary(self) -> str:
        """
        Get a formatted summary of the import process.

        Returns:
            Formatted string with import statistics
        """
        summary = f"""
Data Import Summary
==================
Total Rows: {self.import_stats['total_rows']}
Successful: {self.import_stats['successful']}
Failed: {self.import_stats['failed']}
Skipped: {self.import_stats['skipped']}

Validation Errors: {len(self.validation_errors)}
Import Warnings: {len(self.import_stats['warnings'])}
"""
        return summary


def import_pharmaceutical_data(
    excel_path: str,
    sheet_name: str = 0,
    validate: bool = True,
    clean: bool = True
) -> Dict:
    """
    Convenience function to import pharmaceutical data from Excel.

    Args:
        excel_path: Path to Excel file
        sheet_name: Sheet name or index to load
        validate: Whether to validate data before import
        clean: Whether to clean data before import

    Returns:
        Dictionary with import statistics
    """
    loader = DataLoader(excel_path)

    # Load data
    loader.load_excel(sheet_name)

    # Validate if requested
    if validate:
        is_valid, errors = loader.validate_data()
        if not is_valid and errors:
            logger.warning(f"Validation found {len(errors)} error(s), but continuing...")

    # Clean if requested
    if clean:
        loader.clean_data()

    # Import to database
    db = get_database()
    with db.get_session() as session:
        stats = loader.import_to_database(session)

    # Print summary
    print(loader.get_import_summary())

    return stats


def seed_sample_hospitals(session: Session):
    """
    Seed database with sample hospital data for the lending network.

    Args:
        session: SQLAlchemy session
    """
    sample_hospitals = [
        {
            "name": "King Faisal Specialist Hospital",
            "code": "KFSH",
            "location": "Riyadh",
            "contact_person": "Pharmacy Director",
            "contact_phone": "+966-11-464-7272",
            "contact_email": "pharmacy@kfsh.med.sa"
        },
        {
            "name": "King Khalid University Hospital",
            "code": "KKUH",
            "location": "Riyadh",
            "contact_person": "Chief Pharmacist",
            "contact_phone": "+966-11-467-9222",
            "contact_email": "pharmacy@kkuh.edu.sa"
        },
        {
            "name": "King Abdulaziz Medical City",
            "code": "KAMC",
            "location": "Riyadh",
            "contact_person": "Pharmacy Manager",
            "contact_phone": "+966-11-252-0088",
            "contact_email": "pharmacy@kamc.med.sa"
        }
    ]

    for hospital_data in sample_hospitals:
        # Check if hospital already exists
        existing = session.query(Hospital).filter_by(code=hospital_data["code"]).first()
        if not existing:
            hospital = Hospital(**hospital_data)
            session.add(hospital)

    session.commit()
    logger.info(f"Seeded {len(sample_hospitals)} sample hospitals")
