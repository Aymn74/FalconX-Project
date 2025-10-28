"""
Pharmacogenomics (PGx) analysis module for drug-gene interactions.
"""
import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from pharmintel.core.models import Drug, PharmacogenomicAssociation

logger = logging.getLogger(__name__)


class ClinicalSignificance(Enum):
    """Clinical significance levels for PGx associations."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNCERTAIN = "uncertain"


class EffectType(Enum):
    """Types of pharmacogenomic effects."""
    METABOLISM = "metabolism"
    EFFICACY = "efficacy"
    TOXICITY = "toxicity"
    DOSING = "dosing"
    CONTRAINDICATION = "contraindication"


@dataclass
class PGxInteraction:
    """Pharmacogenomic interaction data structure."""
    drug_name: str
    gene: str
    variant: Optional[str]
    effect_type: str
    effect_description: str
    clinical_significance: str
    recommendation: str
    guideline_source: str
    affected_populations: List[str]
    allele_frequency: Optional[float]


class PharmacogenomicsAnalyzer:
    """Analyzer for pharmacogenomic drug-gene interactions."""

    def __init__(self, session: Session):
        """
        Initialize PGx analyzer.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.pgx_database = self._load_pgx_database()

    def _load_pgx_database(self) -> Dict:
        """
        Load pharmacogenomics database.
        In a production system, this would load from a comprehensive PGx database.

        Returns:
            Dictionary with PGx interaction data
        """
        # Sample PGx database with common drug-gene interactions
        # In production, this would be loaded from PharmGKB, CPIC, or similar databases
        pgx_db = {
            "warfarin": [
                {
                    "gene": "CYP2C9",
                    "variant": "*2, *3",
                    "effect_type": "metabolism",
                    "effect_description": "Reduced metabolism, increased bleeding risk",
                    "clinical_significance": "high",
                    "recommendation": "Consider 25-50% dose reduction. Use pharmacogenetic dosing algorithm.",
                    "guideline_source": "CPIC",
                    "affected_populations": ["European", "Middle Eastern"],
                    "allele_frequency": 0.15
                },
                {
                    "gene": "VKORC1",
                    "variant": "-1639G>A",
                    "effect_type": "sensitivity",
                    "effect_description": "Increased warfarin sensitivity",
                    "clinical_significance": "high",
                    "recommendation": "Consider lower starting dose. Use PGx-guided dosing.",
                    "guideline_source": "CPIC",
                    "affected_populations": ["Asian", "European"],
                    "allele_frequency": 0.40
                }
            ],
            "clopidogrel": [
                {
                    "gene": "CYP2C19",
                    "variant": "*2, *3",
                    "effect_type": "efficacy",
                    "effect_description": "Reduced conversion to active metabolite, decreased antiplatelet effect",
                    "clinical_significance": "high",
                    "recommendation": "Consider alternative antiplatelet therapy (e.g., prasugrel, ticagrelor)",
                    "guideline_source": "CPIC, FDA",
                    "affected_populations": ["Asian (higher frequency)", "European", "Middle Eastern"],
                    "allele_frequency": 0.30
                }
            ],
            "simvastatin": [
                {
                    "gene": "SLCO1B1",
                    "variant": "521T>C (*5)",
                    "effect_type": "toxicity",
                    "effect_description": "Increased myopathy risk",
                    "clinical_significance": "high",
                    "recommendation": "Avoid doses >20mg daily or consider alternative statin",
                    "guideline_source": "CPIC",
                    "affected_populations": ["All populations"],
                    "allele_frequency": 0.15
                }
            ],
            "codeine": [
                {
                    "gene": "CYP2D6",
                    "variant": "Ultra-rapid metabolizer",
                    "effect_type": "toxicity",
                    "effect_description": "Increased conversion to morphine, toxicity risk",
                    "clinical_significance": "high",
                    "recommendation": "Avoid use. Choose alternative analgesic.",
                    "guideline_source": "CPIC, FDA",
                    "affected_populations": ["Middle Eastern (5-10%)", "North African"],
                    "allele_frequency": 0.07
                },
                {
                    "gene": "CYP2D6",
                    "variant": "Poor metabolizer",
                    "effect_type": "efficacy",
                    "effect_description": "Reduced conversion to morphine, lack of efficacy",
                    "clinical_significance": "high",
                    "recommendation": "Avoid use. Choose alternative analgesic.",
                    "guideline_source": "CPIC",
                    "affected_populations": ["Asian (1%)", "European (7%)"],
                    "allele_frequency": 0.07
                }
            ],
            "carbamazepine": [
                {
                    "gene": "HLA-B",
                    "variant": "*15:02",
                    "effect_type": "toxicity",
                    "effect_description": "Severe cutaneous adverse reactions (Stevens-Johnson syndrome)",
                    "clinical_significance": "high",
                    "recommendation": "Test for HLA-B*15:02 before use in at-risk populations. If positive, avoid use.",
                    "guideline_source": "CPIC, FDA",
                    "affected_populations": ["Asian (particularly Han Chinese, Thai, Malaysian)", "South Asian"],
                    "allele_frequency": 0.10
                }
            ],
            "abacavir": [
                {
                    "gene": "HLA-B",
                    "variant": "*57:01",
                    "effect_type": "toxicity",
                    "effect_description": "Hypersensitivity reaction",
                    "clinical_significance": "high",
                    "recommendation": "Test for HLA-B*57:01 before use. If positive, do not use.",
                    "guideline_source": "CPIC, FDA",
                    "affected_populations": ["European (5-8%)", "Middle Eastern"],
                    "allele_frequency": 0.06
                }
            ],
            "azathioprine": [
                {
                    "gene": "TPMT",
                    "variant": "Poor metabolizer",
                    "effect_type": "toxicity",
                    "effect_description": "Severe myelosuppression",
                    "clinical_significance": "high",
                    "recommendation": "Reduce starting dose by 90% or consider alternative therapy",
                    "guideline_source": "CPIC, FDA",
                    "affected_populations": ["European (0.3%)", "Asian (0.03%)"],
                    "allele_frequency": 0.003
                }
            ],
            "tamoxifen": [
                {
                    "gene": "CYP2D6",
                    "variant": "Poor metabolizer",
                    "effect_type": "efficacy",
                    "effect_description": "Reduced conversion to active metabolite, decreased efficacy",
                    "clinical_significance": "moderate",
                    "recommendation": "Consider alternative hormonal therapy",
                    "guideline_source": "CPIC",
                    "affected_populations": ["Asian (1%)", "European (7%)"],
                    "allele_frequency": 0.07
                }
            ]
        }

        return pgx_db

    def analyze_drug(self, drug_name: str, population: Optional[str] = None) -> List[PGxInteraction]:
        """
        Analyze pharmacogenomic interactions for a specific drug.

        Args:
            drug_name: Name of the drug to analyze
            population: Optional population filter (e.g., "Middle Eastern", "Asian")

        Returns:
            List of PGxInteraction objects
        """
        interactions = []
        drug_name_lower = drug_name.lower()

        # Find matching drug in PGx database
        for drug_key, pgx_data in self.pgx_database.items():
            if drug_key in drug_name_lower or drug_name_lower in drug_key:
                for interaction in pgx_data:
                    # Filter by population if specified
                    if population and population not in interaction.get("affected_populations", []):
                        continue

                    pgx_interaction = PGxInteraction(
                        drug_name=drug_name,
                        gene=interaction["gene"],
                        variant=interaction.get("variant"),
                        effect_type=interaction["effect_type"],
                        effect_description=interaction["effect_description"],
                        clinical_significance=interaction["clinical_significance"],
                        recommendation=interaction["recommendation"],
                        guideline_source=interaction["guideline_source"],
                        affected_populations=interaction["affected_populations"],
                        allele_frequency=interaction.get("allele_frequency")
                    )
                    interactions.append(pgx_interaction)

        return interactions

    def get_high_priority_interactions(self, therapeutic_area: Optional[str] = None) -> List[Dict]:
        """
        Get all high-priority (high clinical significance) PGx interactions.

        Args:
            therapeutic_area: Optional filter by therapeutic area

        Returns:
            List of high-priority interactions
        """
        high_priority = []

        drugs = self.session.query(Drug).all()

        for drug in drugs:
            if therapeutic_area and str(drug.therapeutic_area.value) != therapeutic_area:
                continue

            interactions = self.analyze_drug(drug.material)
            for interaction in interactions:
                if interaction.clinical_significance == "high":
                    high_priority.append({
                        "drug_id": drug.id,
                        "drug_name": drug.material,
                        "material_number": drug.material_number,
                        "interaction": interaction
                    })

        return high_priority

    def generate_pgx_report(self, drug_id: int) -> Dict:
        """
        Generate comprehensive PGx report for a specific drug.

        Args:
            drug_id: Database ID of the drug

        Returns:
            Dictionary containing PGx report data
        """
        drug = self.session.query(Drug).filter_by(id=drug_id).first()

        if not drug:
            raise ValueError(f"Drug with ID {drug_id} not found")

        interactions = self.analyze_drug(drug.material)

        report = {
            "drug_info": {
                "id": drug.id,
                "name": drug.material,
                "material_number": drug.material_number,
                "therapeutic_area": drug.therapeutic_area.value if drug.therapeutic_area else None,
                "atc_code": drug.atc_code
            },
            "pgx_summary": {
                "total_interactions": len(interactions),
                "high_significance": sum(1 for i in interactions if i.clinical_significance == "high"),
                "moderate_significance": sum(1 for i in interactions if i.clinical_significance == "moderate"),
                "low_significance": sum(1 for i in interactions if i.clinical_significance == "low")
            },
            "interactions": [
                {
                    "gene": i.gene,
                    "variant": i.variant,
                    "effect_type": i.effect_type,
                    "effect_description": i.effect_description,
                    "clinical_significance": i.clinical_significance,
                    "recommendation": i.recommendation,
                    "guideline_source": i.guideline_source,
                    "affected_populations": i.affected_populations,
                    "allele_frequency": i.allele_frequency
                }
                for i in interactions
            ],
            "clinical_recommendations": self._generate_clinical_recommendations(interactions),
            "population_considerations": self._generate_population_considerations(interactions)
        }

        return report

    def _generate_clinical_recommendations(self, interactions: List[PGxInteraction]) -> List[str]:
        """Generate clinical recommendations based on interactions."""
        recommendations = []

        high_sig = [i for i in interactions if i.clinical_significance == "high"]

        if high_sig:
            recommendations.append(
                "HIGH PRIORITY: This drug has high-significance pharmacogenomic interactions. "
                "Genetic testing is strongly recommended before prescribing."
            )

            for interaction in high_sig:
                recommendations.append(
                    f"• {interaction.gene}: {interaction.recommendation}"
                )
        elif interactions:
            recommendations.append(
                "Consider pharmacogenomic testing for optimal dosing and reduced adverse effects."
            )
        else:
            recommendations.append(
                "No major pharmacogenomic interactions found in database. "
                "Follow standard prescribing guidelines."
            )

        return recommendations

    def _generate_population_considerations(self, interactions: List[PGxInteraction]) -> Dict:
        """Generate population-specific considerations."""
        populations = {}

        for interaction in interactions:
            for pop in interaction.affected_populations:
                if pop not in populations:
                    populations[pop] = []

                populations[pop].append({
                    "gene": interaction.gene,
                    "variant": interaction.variant,
                    "significance": interaction.clinical_significance,
                    "allele_frequency": interaction.allele_frequency
                })

        return populations

    def bulk_analyze_formulary(self) -> Dict:
        """
        Analyze entire formulary for pharmacogenomic considerations.

        Returns:
            Summary statistics and findings
        """
        logger.info("Starting bulk PGx analysis of formulary...")

        drugs = self.session.query(Drug).all()
        results = {
            "total_drugs": len(drugs),
            "drugs_with_pgx": 0,
            "high_priority_drugs": [],
            "by_therapeutic_area": {},
            "by_gene": {}
        }

        for drug in drugs:
            interactions = self.analyze_drug(drug.material)

            if interactions:
                results["drugs_with_pgx"] += 1

                # Track by therapeutic area
                area = drug.therapeutic_area.value if drug.therapeutic_area else "Unknown"
                if area not in results["by_therapeutic_area"]:
                    results["by_therapeutic_area"][area] = 0
                results["by_therapeutic_area"][area] += 1

                # Track by gene
                for interaction in interactions:
                    if interaction.gene not in results["by_gene"]:
                        results["by_gene"][interaction.gene] = []
                    results["by_gene"][interaction.gene].append(drug.material)

                # High priority drugs
                if any(i.clinical_significance == "high" for i in interactions):
                    results["high_priority_drugs"].append({
                        "id": drug.id,
                        "name": drug.material,
                        "material_number": drug.material_number,
                        "interaction_count": len(interactions)
                    })

        logger.info(f"PGx analysis complete. Found {results['drugs_with_pgx']} drugs with PGx interactions.")
        return results

    def get_arab_population_considerations(self) -> List[Dict]:
        """
        Get specific pharmacogenomic considerations for Arab populations.

        Returns:
            List of drugs with special considerations for Arab populations
        """
        considerations = []

        drugs = self.session.query(Drug).all()

        for drug in drugs:
            interactions = self.analyze_drug(drug.material, population="Middle Eastern")

            if interactions:
                considerations.append({
                    "drug": drug.material,
                    "material_number": drug.material_number,
                    "interactions": [
                        {
                            "gene": i.gene,
                            "variant": i.variant,
                            "significance": i.clinical_significance,
                            "recommendation": i.recommendation
                        }
                        for i in interactions
                    ]
                })

        return considerations
