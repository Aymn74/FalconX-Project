"""
Enhancement recommendation system for formulary optimization.
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func
from pharmintel.core.models import Drug, EnhancementRecommendation, FormularyStatus
from pharmintel.config import COST_OPTIMIZATION_THRESHOLD

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Types of enhancement recommendations."""
    BIOSIMILAR_OPPORTUNITY = "biosimilar_opportunity"
    GENERIC_SUBSTITUTION = "generic_substitution"
    DUPLICATE_CONSOLIDATION = "duplicate_consolidation"
    EVIDENCE_BASED_ADDITION = "evidence_based_addition"
    THERAPEUTIC_INTERCHANGE = "therapeutic_interchange"
    GUIDELINE_COMPLIANCE = "guideline_compliance"
    COST_OPTIMIZATION = "cost_optimization"


class EvidenceGrade(Enum):
    """Evidence grades for recommendations."""
    GRADE_A = "A"  # High quality evidence
    GRADE_B = "B"  # Moderate quality evidence
    GRADE_C = "C"  # Low quality evidence
    GRADE_D = "D"  # Expert opinion


@dataclass
class Recommendation:
    """Enhancement recommendation data structure."""
    recommendation_type: str
    current_drug: Optional[str]
    current_drug_id: Optional[int]
    suggested_drug: str
    rationale: str
    estimated_savings: Optional[float]
    evidence_grade: str
    priority: int
    implementation_complexity: str


class EnhancementAnalyzer:
    """Analyzer for formulary enhancement opportunities."""

    def __init__(self, session: Session):
        """
        Initialize enhancement analyzer.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.biosimilar_pairs = self._load_biosimilar_database()
        self.generic_pairs = self._load_generic_database()
        self.therapeutic_classes = self._load_therapeutic_classes()

    def _load_biosimilar_database(self) -> Dict:
        """Load biosimilar opportunity database."""
        # Common biosimilar opportunities
        biosimilars = {
            "Infliximab": {
                "biosimilars": ["Infliximab-dyyb", "Infliximab-abda"],
                "savings_percentage": 35,
                "evidence_grade": "A",
                "notes": "Multiple biosimilars approved with comparable efficacy"
            },
            "Rituximab": {
                "biosimilars": ["Rituximab-abbs", "Rituximab-pvvr"],
                "savings_percentage": 30,
                "evidence_grade": "A",
                "notes": "FDA-approved biosimilars available"
            },
            "Adalimumab": {
                "biosimilars": ["Adalimumab-atto", "Adalimumab-adaz"],
                "savings_percentage": 40,
                "evidence_grade": "A",
                "notes": "Multiple biosimilars with significant cost savings"
            },
            "Trastuzumab": {
                "biosimilars": ["Trastuzumab-anns", "Trastuzumab-dkst"],
                "savings_percentage": 30,
                "evidence_grade": "A",
                "notes": "Biosimilars approved for all indications"
            },
            "Bevacizumab": {
                "biosimilars": ["Bevacizumab-awwb"],
                "savings_percentage": 25,
                "evidence_grade": "B",
                "notes": "Growing biosimilar availability"
            }
        }
        return biosimilars

    def _load_generic_database(self) -> Dict:
        """Load generic substitution opportunities."""
        # Common generic opportunities (brand to generic)
        generics = {
            "Nexium": {
                "generic": "Esomeprazole",
                "savings_percentage": 80,
                "therapeutic_equivalence": "AB"
            },
            "Lipitor": {
                "generic": "Atorvastatin",
                "savings_percentage": 85,
                "therapeutic_equivalence": "AB"
            },
            "Plavix": {
                "generic": "Clopidogrel",
                "savings_percentage": 75,
                "therapeutic_equivalence": "AB"
            },
            "Crestor": {
                "generic": "Rosuvastatin",
                "savings_percentage": 80,
                "therapeutic_equivalence": "AB"
            }
        }
        return generics

    def _load_therapeutic_classes(self) -> Dict:
        """Load therapeutic class information for duplicate analysis."""
        classes = {
            "PPI": ["Omeprazole", "Pantoprazole", "Esomeprazole", "Lansoprazole", "Rabeprazole"],
            "ACE Inhibitors": ["Enalapril", "Lisinopril", "Ramipril", "Perindopril"],
            "ARBs": ["Losartan", "Valsartan", "Irbesartan", "Telmisartan"],
            "Beta Blockers": ["Atenolol", "Bisoprolol", "Metoprolol", "Carvedilol"],
            "Statins": ["Atorvastatin", "Simvastatin", "Rosuvastatin", "Pravastatin"],
            "SSRIs": ["Fluoxetine", "Sertraline", "Escitalopram", "Paroxetine"],
            "Cephalosporins (3rd gen)": ["Ceftriaxone", "Cefotaxime", "Ceftazidime"],
            "NSAIDs": ["Ibuprofen", "Naproxen", "Diclofenac", "Celecoxib"]
        }
        return classes

    def identify_biosimilar_opportunities(self) -> List[Recommendation]:
        """
        Identify biosimilar opportunities.

        Returns:
            List of biosimilar recommendations
        """
        recommendations = []
        drugs = self.session.query(Drug).all()

        for drug in drugs:
            drug_name = drug.material

            # Check if drug has biosimilar opportunity
            for original, data in self.biosimilar_pairs.items():
                if original.lower() in drug_name.lower():
                    biosimilars = data["biosimilars"]

                    # Check if biosimilar already in formulary
                    has_biosimilar = any(
                        self.session.query(Drug).filter(
                            Drug.material.contains(biosim)
                        ).first() for biosim in biosimilars
                    )

                    if not has_biosimilar:
                        estimated_savings = None
                        if drug.cost_per_unit:
                            estimated_savings = drug.cost_per_unit * (data["savings_percentage"] / 100)

                        rec = Recommendation(
                            recommendation_type=RecommendationType.BIOSIMILAR_OPPORTUNITY.value,
                            current_drug=drug_name,
                            current_drug_id=drug.id,
                            suggested_drug=", ".join(biosimilars),
                            rationale=f"Biosimilar available with ~{data['savings_percentage']}% cost savings. {data['notes']}",
                            estimated_savings=estimated_savings,
                            evidence_grade=data["evidence_grade"],
                            priority=8,
                            implementation_complexity="Medium"
                        )
                        recommendations.append(rec)

        return recommendations

    def identify_generic_opportunities(self) -> List[Recommendation]:
        """
        Identify generic substitution opportunities.

        Returns:
            List of generic substitution recommendations
        """
        recommendations = []
        drugs = self.session.query(Drug).all()

        for drug in drugs:
            drug_name = drug.material

            # Check if drug has generic opportunity
            for brand, data in self.generic_pairs.items():
                if brand.lower() in drug_name.lower():
                    # Check if generic already in formulary
                    has_generic = self.session.query(Drug).filter(
                        Drug.material.contains(data["generic"])
                    ).first()

                    if not has_generic:
                        estimated_savings = None
                        if drug.cost_per_unit:
                            estimated_savings = drug.cost_per_unit * (data["savings_percentage"] / 100)

                        rec = Recommendation(
                            recommendation_type=RecommendationType.GENERIC_SUBSTITUTION.value,
                            current_drug=drug_name,
                            current_drug_id=drug.id,
                            suggested_drug=data["generic"],
                            rationale=f"Generic available with ~{data['savings_percentage']}% cost savings. "
                                      f"Therapeutic equivalence: {data['therapeutic_equivalence']}",
                            estimated_savings=estimated_savings,
                            evidence_grade=EvidenceGrade.GRADE_A.value,
                            priority=9,
                            implementation_complexity="Low"
                        )
                        recommendations.append(rec)

        return recommendations

    def identify_duplicate_classes(self) -> List[Recommendation]:
        """
        Identify duplicate therapeutic classes for consolidation.

        Returns:
            List of consolidation recommendations
        """
        recommendations = []

        for class_name, class_drugs in self.therapeutic_classes.items():
            # Find drugs from this class in formulary
            formulary_drugs_in_class = []

            for drug in self.session.query(Drug).all():
                for class_drug in class_drugs:
                    if class_drug.lower() in drug.material.lower():
                        formulary_drugs_in_class.append(drug)
                        break

            # If more than 3 drugs from same class, suggest consolidation
            if len(formulary_drugs_in_class) > 3:
                # Sort by cost if available
                if all(d.cost_per_unit for d in formulary_drugs_in_class):
                    formulary_drugs_in_class.sort(key=lambda x: x.cost_per_unit or 0)

                drugs_to_keep = formulary_drugs_in_class[:2]  # Keep top 2
                drugs_to_remove = formulary_drugs_in_class[2:]  # Remove rest

                rec = Recommendation(
                    recommendation_type=RecommendationType.DUPLICATE_CONSOLIDATION.value,
                    current_drug=f"{len(formulary_drugs_in_class)} drugs in {class_name}",
                    current_drug_id=None,
                    suggested_drug=f"Consolidate to: {', '.join(d.material for d in drugs_to_keep)}",
                    rationale=f"Excessive duplication in {class_name}. Consolidation reduces "
                              f"complexity and potential errors.",
                    estimated_savings=None,
                    evidence_grade=EvidenceGrade.GRADE_B.value,
                    priority=6,
                    implementation_complexity="Medium"
                )
                recommendations.append(rec)

        return recommendations

    def identify_cost_optimization(self, threshold: float = COST_OPTIMIZATION_THRESHOLD) -> List[Recommendation]:
        """
        Identify cost optimization opportunities.

        Args:
            threshold: Minimum savings percentage to recommend (default 15%)

        Returns:
            List of cost optimization recommendations
        """
        recommendations = []

        # Find drugs with high costs that might have alternatives
        expensive_drugs = self.session.query(Drug).filter(
            Drug.cost_per_unit.isnot(None)
        ).order_by(Drug.cost_per_unit.desc()).limit(50).all()

        for drug in expensive_drugs:
            # Check for therapeutic alternatives
            similar_drugs = self.session.query(Drug).filter(
                Drug.therapeutic_area == drug.therapeutic_area,
                Drug.atc_level_2 == drug.atc_level_2,
                Drug.id != drug.id,
                Drug.cost_per_unit.isnot(None),
                Drug.cost_per_unit < drug.cost_per_unit * (1 - threshold)
            ).all()

            if similar_drugs:
                cheapest = min(similar_drugs, key=lambda x: x.cost_per_unit or float('inf'))
                savings_pct = ((drug.cost_per_unit - cheapest.cost_per_unit) / drug.cost_per_unit) * 100

                rec = Recommendation(
                    recommendation_type=RecommendationType.COST_OPTIMIZATION.value,
                    current_drug=drug.material,
                    current_drug_id=drug.id,
                    suggested_drug=cheapest.material,
                    rationale=f"Alternative available with {savings_pct:.1f}% cost savings in same therapeutic class",
                    estimated_savings=drug.cost_per_unit - cheapest.cost_per_unit,
                    evidence_grade=EvidenceGrade.GRADE_B.value,
                    priority=7,
                    implementation_complexity="Low"
                )
                recommendations.append(rec)

        return recommendations

    def check_guideline_compliance(self) -> List[Recommendation]:
        """
        Check formulary compliance with treatment guidelines.

        Returns:
            List of guideline compliance recommendations
        """
        recommendations = []

        # Common guideline-recommended first-line therapies
        guidelines = {
            "Hypertension": {
                "recommended": ["Amlodipine", "Lisinopril", "Losartan"],
                "guideline": "JNC 8"
            },
            "Type 2 Diabetes": {
                "recommended": ["Metformin", "Empagliflozin", "Liraglutide"],
                "guideline": "ADA Standards of Care"
            },
            "Heart Failure": {
                "recommended": ["Sacubitril-Valsartan", "Carvedilol", "Spironolactone"],
                "guideline": "ACC/AHA Guidelines"
            },
            "COPD": {
                "recommended": ["Tiotropium", "Formoterol", "Budesonide-Formoterol"],
                "guideline": "GOLD Guidelines"
            }
        }

        for condition, data in guidelines.items():
            missing_drugs = []

            for recommended_drug in data["recommended"]:
                # Check if drug is in formulary
                drug_exists = self.session.query(Drug).filter(
                    Drug.material.contains(recommended_drug)
                ).first()

                if not drug_exists:
                    missing_drugs.append(recommended_drug)

            if missing_drugs:
                rec = Recommendation(
                    recommendation_type=RecommendationType.GUIDELINE_COMPLIANCE.value,
                    current_drug=None,
                    current_drug_id=None,
                    suggested_drug=", ".join(missing_drugs),
                    rationale=f"{data['guideline']} recommends these as first-line therapy for {condition}",
                    estimated_savings=None,
                    evidence_grade=EvidenceGrade.GRADE_A.value,
                    priority=8,
                    implementation_complexity="Low"
                )
                recommendations.append(rec)

        return recommendations

    def generate_all_recommendations(self) -> Dict[str, List[Recommendation]]:
        """
        Generate all types of recommendations.

        Returns:
            Dictionary organized by recommendation type
        """
        logger.info("Generating enhancement recommendations...")

        recommendations = {
            "biosimilar": self.identify_biosimilar_opportunities(),
            "generic": self.identify_generic_opportunities(),
            "duplicate": self.identify_duplicate_classes(),
            "cost": self.identify_cost_optimization(),
            "guideline": self.check_guideline_compliance()
        }

        # Calculate totals
        total_recs = sum(len(recs) for recs in recommendations.values())
        logger.info(f"Generated {total_recs} enhancement recommendations")

        return recommendations

    def save_recommendations_to_database(self, recommendations: Dict[str, List[Recommendation]]):
        """
        Save recommendations to database.

        Args:
            recommendations: Dictionary of recommendations by type
        """
        count = 0

        for rec_type, rec_list in recommendations.items():
            for rec in rec_list:
                db_rec = EnhancementRecommendation(
                    recommendation_type=rec.recommendation_type,
                    current_drug_id=rec.current_drug_id,
                    suggested_drug_name=rec.suggested_drug,
                    rationale=rec.rationale,
                    estimated_savings=rec.estimated_savings,
                    evidence_grade=rec.evidence_grade,
                    status="pending"
                )
                self.session.add(db_rec)
                count += 1

        self.session.commit()
        logger.info(f"Saved {count} recommendations to database")

    def calculate_total_savings_potential(self, recommendations: Dict[str, List[Recommendation]]) -> Dict:
        """
        Calculate total potential savings from all recommendations.

        Args:
            recommendations: Dictionary of recommendations

        Returns:
            Dictionary with savings analysis
        """
        total_savings = 0
        savings_by_type = defaultdict(float)
        count_with_savings = 0

        for rec_type, rec_list in recommendations.items():
            for rec in rec_list:
                if rec.estimated_savings:
                    total_savings += rec.estimated_savings
                    savings_by_type[rec_type] += rec.estimated_savings
                    count_with_savings += 1

        return {
            "total_potential_savings": round(total_savings, 2),
            "recommendations_with_savings": count_with_savings,
            "savings_by_type": dict(savings_by_type),
            "average_savings": round(total_savings / count_with_savings, 2) if count_with_savings > 0 else 0
        }

    def generate_summary_report(self) -> Dict:
        """
        Generate summary report of all enhancement opportunities.

        Returns:
            Dictionary with comprehensive summary
        """
        recommendations = self.generate_all_recommendations()
        savings_potential = self.calculate_total_savings_potential(recommendations)

        # Count by priority
        all_recs = []
        for rec_list in recommendations.values():
            all_recs.extend(rec_list)

        high_priority = [r for r in all_recs if r.priority >= 8]
        medium_priority = [r for r in all_recs if 5 <= r.priority < 8]
        low_priority = [r for r in all_recs if r.priority < 5]

        report = {
            "summary": {
                "total_recommendations": len(all_recs),
                "high_priority": len(high_priority),
                "medium_priority": len(medium_priority),
                "low_priority": len(low_priority)
            },
            "by_type": {
                rec_type: len(rec_list)
                for rec_type, rec_list in recommendations.items()
            },
            "savings_potential": savings_potential,
            "recommendations": recommendations,
            "top_opportunities": sorted(all_recs, key=lambda x: x.priority, reverse=True)[:10]
        }

        return report
