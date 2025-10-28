"""
Formulary gap analysis engine.
Compares formulary against WHO Essential Medicines List and identifies coverage gaps.
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func
from pharmintel.core.models import (
    Drug, TherapeuticArea, GapAnalysisResult, WHOEssentialMedicine
)

logger = logging.getLogger(__name__)


class GapSeverity(Enum):
    """Gap severity classifications."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GapType(Enum):
    """Types of formulary gaps."""
    MISSING_WHO_ESSENTIAL = "missing_who_essential"
    MISSING_THERAPEUTIC_CLASS = "missing_therapeutic_class"
    LOW_COVERAGE = "low_coverage"
    SINGLE_AGENT_DEPENDENCY = "single_agent_dependency"
    NO_ALTERNATIVE = "no_alternative"
    DISEASE_MISMATCH = "disease_mismatch"


@dataclass
class Gap:
    """Represents a formulary gap."""
    gap_type: str
    therapeutic_area: str
    severity: str
    description: str
    recommendation: str
    missing_drugs: List[str]
    priority_score: float
    estimated_cost_impact: Optional[float] = None


class FormularyGapAnalyzer:
    """Analyzer for identifying gaps in pharmaceutical formulary."""

    def __init__(self, session: Session):
        """
        Initialize gap analyzer.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.who_essential_list = self._load_who_essential_medicines()

    def _load_who_essential_medicines(self) -> Dict:
        """
        Load WHO Essential Medicines List.
        In production, this would be loaded from WHO database or API.

        Returns:
            Dictionary organized by therapeutic area
        """
        # Sample WHO Essential Medicines (subset)
        # In production, load from WHO EML database
        who_eml = {
            "Cardiology": [
                "Atenolol", "Bisoprolol", "Carvedilol",
                "Amlodipine", "Enalapril", "Lisinopril",
                "Atorvastatin", "Simvastatin",
                "Aspirin", "Clopidogrel",
                "Warfarin", "Heparin",
                "Furosemide", "Spironolactone",
                "Digoxin", "Amiodarone"
            ],
            "Infectious Disease": [
                "Amoxicillin", "Ampicillin",
                "Ceftriaxone", "Cefixime",
                "Ciprofloxacin", "Azithromycin",
                "Metronidazole", "Vancomycin",
                "Acyclovir", "Oseltamivir",
                "Fluconazole", "Itraconazole"
            ],
            "Internal Medicine": [
                "Metformin", "Glibenclamide", "Insulin",
                "Levothyroxine",
                "Omeprazole", "Ranitidine",
                "Metoclopramide",
                "Prednisolone", "Hydrocortisone"
            ],
            "Neuropsychiatry": [
                "Levetiracetam", "Carbamazepine", "Valproic Acid",
                "Phenytoin", "Phenobarbital",
                "Haloperidol", "Risperidone",
                "Fluoxetine", "Sertraline",
                "Diazepam", "Lorazepam",
                "Levodopa", "Donepezil"
            ],
            "Oncology": [
                "Cyclophosphamide", "Doxorubicin",
                "Fluorouracil", "Methotrexate",
                "Paclitaxel", "Cisplatin",
                "Tamoxifen", "Imatinib",
                "Filgrastim", "Ondansetron"
            ],
            "Critical Care": [
                "Epinephrine", "Norepinephrine",
                "Dopamine", "Dobutamine",
                "Midazolam", "Propofol",
                "Morphine", "Fentanyl",
                "Atropine", "Naloxone",
                "Hydralazine", "Labetalol"
            ],
            "Immunology": [
                "Methotrexate", "Azathioprine",
                "Cyclosporine", "Tacrolimus",
                "Infliximab", "Adalimumab",
                "Rituximab",
                "Immunoglobulin (IVIG)"
            ],
            "GI & Hormonal": [
                "Omeprazole", "Pantoprazole",
                "Mesalamine", "Sulfasalazine",
                "Lactulose", "Bisacodyl",
                "Metformin", "Insulin",
                "Levothyroxine", "Carbimazole",
                "Prednisolone", "Hydrocortisone"
            ]
        }

        return who_eml

    def analyze_therapeutic_area_coverage(self, therapeutic_area: str) -> Dict:
        """
        Analyze coverage for a specific therapeutic area.

        Args:
            therapeutic_area: Name of therapeutic area

        Returns:
            Dictionary with coverage analysis
        """
        # Get drugs in this therapeutic area from formulary
        drugs = self.session.query(Drug).filter(
            Drug.therapeutic_area == TherapeuticArea[therapeutic_area.upper().replace(" ", "_")]
        ).all()

        # Get WHO essential medicines for this area
        who_drugs = self.who_essential_list.get(therapeutic_area, [])

        # Analyze coverage
        formulary_drugs = [d.material.lower() for d in drugs]
        missing_drugs = []

        for who_drug in who_drugs:
            # Check if WHO drug is in formulary (fuzzy matching)
            found = any(who_drug.lower() in fd or fd in who_drug.lower() for fd in formulary_drugs)
            if not found:
                missing_drugs.append(who_drug)

        coverage_percentage = ((len(who_drugs) - len(missing_drugs)) / len(who_drugs) * 100) if who_drugs else 0

        return {
            "therapeutic_area": therapeutic_area,
            "formulary_drug_count": len(drugs),
            "who_essential_count": len(who_drugs),
            "missing_count": len(missing_drugs),
            "coverage_percentage": round(coverage_percentage, 2),
            "missing_drugs": missing_drugs,
            "formulary_drugs": [d.material for d in drugs[:10]]  # Sample
        }

    def identify_gaps(self) -> List[Gap]:
        """
        Identify all gaps in the formulary.

        Returns:
            List of Gap objects
        """
        gaps = []

        # Analyze each therapeutic area
        for area in TherapeuticArea:
            area_name = area.value

            # Skip "Other" category
            if area_name == "Other":
                continue

            coverage = self.analyze_therapeutic_area_coverage(area_name)

            # Gap 1: Missing WHO Essential Medicines
            if coverage["missing_drugs"]:
                severity = self._calculate_severity(coverage["coverage_percentage"])
                priority = self._calculate_priority_score(
                    severity=severity,
                    missing_count=coverage["missing_count"],
                    area_importance=self._get_area_importance(area_name)
                )

                gap = Gap(
                    gap_type=GapType.MISSING_WHO_ESSENTIAL.value,
                    therapeutic_area=area_name,
                    severity=severity,
                    description=f"Missing {coverage['missing_count']} WHO Essential Medicines "
                                f"({100 - coverage['coverage_percentage']:.1f}% gap)",
                    recommendation=f"Consider adding: {', '.join(coverage['missing_drugs'][:5])}",
                    missing_drugs=coverage["missing_drugs"],
                    priority_score=priority
                )
                gaps.append(gap)

            # Gap 2: Low coverage (<70%)
            if coverage["coverage_percentage"] < 70 and coverage["who_essential_count"] > 0:
                gap = Gap(
                    gap_type=GapType.LOW_COVERAGE.value,
                    therapeutic_area=area_name,
                    severity=GapSeverity.HIGH.value,
                    description=f"Low WHO EML coverage: {coverage['coverage_percentage']:.1f}%",
                    recommendation="Comprehensive review and expansion needed",
                    missing_drugs=coverage["missing_drugs"],
                    priority_score=8.5
                )
                gaps.append(gap)

            # Gap 3: Very small formulary (<5 drugs)
            if coverage["formulary_drug_count"] < 5 and area_name in ["Critical Care", "Infectious Disease"]:
                gap = Gap(
                    gap_type=GapType.MISSING_THERAPEUTIC_CLASS.value,
                    therapeutic_area=area_name,
                    severity=GapSeverity.CRITICAL.value,
                    description=f"Critically low drug count: only {coverage['formulary_drug_count']} drugs",
                    recommendation="Urgent expansion required for this critical therapeutic area",
                    missing_drugs=[],
                    priority_score=9.5
                )
                gaps.append(gap)

        # Sort gaps by priority score
        gaps.sort(key=lambda x: x.priority_score, reverse=True)

        return gaps

    def _calculate_severity(self, coverage_percentage: float) -> str:
        """Calculate gap severity based on coverage percentage."""
        if coverage_percentage < 50:
            return GapSeverity.CRITICAL.value
        elif coverage_percentage < 70:
            return GapSeverity.HIGH.value
        elif coverage_percentage < 85:
            return GapSeverity.MEDIUM.value
        else:
            return GapSeverity.LOW.value

    def _calculate_priority_score(self, severity: str, missing_count: int, area_importance: float) -> float:
        """
        Calculate priority score for a gap (0-10).

        Args:
            severity: Gap severity
            missing_count: Number of missing drugs
            area_importance: Importance score of therapeutic area (0-1)

        Returns:
            Priority score between 0 and 10
        """
        severity_scores = {
            GapSeverity.CRITICAL.value: 10,
            GapSeverity.HIGH.value: 7,
            GapSeverity.MEDIUM.value: 5,
            GapSeverity.LOW.value: 3
        }

        base_score = severity_scores.get(severity, 5)
        missing_factor = min(missing_count / 10, 1.0)  # Cap at 1.0
        priority = base_score * (0.6 + 0.4 * area_importance) * (0.8 + 0.2 * missing_factor)

        return round(min(priority, 10.0), 2)

    def _get_area_importance(self, therapeutic_area: str) -> float:
        """
        Get importance score for therapeutic area (0-1).

        Args:
            therapeutic_area: Name of therapeutic area

        Returns:
            Importance score
        """
        importance = {
            "Critical Care": 1.0,
            "Cardiology": 0.95,
            "Infectious Disease": 0.95,
            "Oncology": 0.90,
            "Neuropsychiatry": 0.85,
            "Internal Medicine": 0.85,
            "Immunology": 0.80,
            "GI & Hormonal": 0.75
        }

        return importance.get(therapeutic_area, 0.70)

    def generate_coverage_heatmap_data(self) -> Dict:
        """
        Generate data for coverage heatmap visualization.

        Returns:
            Dictionary with heatmap data
        """
        heatmap_data = {
            "areas": [],
            "coverage": [],
            "drug_counts": [],
            "missing_counts": []
        }

        for area in TherapeuticArea:
            if area.value == "Other":
                continue

            coverage = self.analyze_therapeutic_area_coverage(area.value)

            heatmap_data["areas"].append(area.value)
            heatmap_data["coverage"].append(coverage["coverage_percentage"])
            heatmap_data["drug_counts"].append(coverage["formulary_drug_count"])
            heatmap_data["missing_counts"].append(coverage["missing_count"])

        return heatmap_data

    def compare_with_benchmark(self, benchmark_formulary: Dict) -> Dict:
        """
        Compare formulary with a benchmark (e.g., peer hospital).

        Args:
            benchmark_formulary: Dictionary with benchmark data

        Returns:
            Comparison results
        """
        comparison = {
            "areas": [],
            "current_counts": [],
            "benchmark_counts": [],
            "gaps": []
        }

        for area in TherapeuticArea:
            if area.value == "Other":
                continue

            current_count = self.session.query(Drug).filter(
                Drug.therapeutic_area == area
            ).count()

            benchmark_count = benchmark_formulary.get(area.value, 0)

            comparison["areas"].append(area.value)
            comparison["current_counts"].append(current_count)
            comparison["benchmark_counts"].append(benchmark_count)

            if current_count < benchmark_count:
                gap = benchmark_count - current_count
                comparison["gaps"].append({
                    "area": area.value,
                    "gap": gap,
                    "percentage": round((gap / benchmark_count) * 100, 2)
                })

        return comparison

    def analyze_atc_coverage(self) -> Dict:
        """
        Analyze coverage by ATC (Anatomical Therapeutic Chemical) classification.

        Returns:
            Dictionary with ATC coverage analysis
        """
        atc_coverage = defaultdict(lambda: {"total": 0, "drugs": []})

        drugs = self.session.query(Drug).all()

        for drug in drugs:
            if drug.atc_level_1:
                atc_coverage[drug.atc_level_1]["total"] += 1
                atc_coverage[drug.atc_level_1]["drugs"].append(drug.material)

        # Convert to regular dict and sort
        result = dict(atc_coverage)
        sorted_result = dict(sorted(result.items(), key=lambda x: x[1]["total"], reverse=True))

        return sorted_result

    def disease_prevalence_analysis(self, disease_data: Dict[str, float]) -> List[Dict]:
        """
        Analyze mismatch between disease prevalence and drug availability.

        Args:
            disease_data: Dictionary mapping disease to prevalence percentage

        Returns:
            List of mismatches
        """
        mismatches = []

        # Map diseases to therapeutic areas (simplified)
        disease_area_map = {
            "diabetes": "Internal Medicine",
            "hypertension": "Cardiology",
            "depression": "Neuropsychiatry",
            "infections": "Infectious Disease",
            "cancer": "Oncology"
        }

        for disease, prevalence in disease_data.items():
            area = disease_area_map.get(disease.lower())
            if area:
                coverage = self.analyze_therapeutic_area_coverage(area)

                # High prevalence but low drug count = mismatch
                if prevalence > 10 and coverage["formulary_drug_count"] < 10:
                    mismatches.append({
                        "disease": disease,
                        "prevalence_percentage": prevalence,
                        "therapeutic_area": area,
                        "drug_count": coverage["formulary_drug_count"],
                        "severity": "high",
                        "recommendation": f"Expand formulary for {area} to match disease burden"
                    })

        return mismatches

    def save_gaps_to_database(self, gaps: List[Gap]):
        """
        Save identified gaps to database.

        Args:
            gaps: List of Gap objects to save
        """
        for gap in gaps:
            gap_result = GapAnalysisResult(
                therapeutic_area=gap.therapeutic_area,
                gap_type=gap.gap_type,
                description=gap.description,
                severity=gap.severity,
                recommendation=gap.recommendation,
                priority_score=gap.priority_score,
                estimated_cost_impact=gap.estimated_cost_impact
            )
            self.session.add(gap_result)

        self.session.commit()
        logger.info(f"Saved {len(gaps)} gap analysis results to database")

    def generate_comprehensive_report(self) -> Dict:
        """
        Generate comprehensive gap analysis report.

        Returns:
            Dictionary with complete gap analysis
        """
        logger.info("Generating comprehensive gap analysis report...")

        gaps = self.identify_gaps()
        heatmap_data = self.generate_coverage_heatmap_data()
        atc_coverage = self.analyze_atc_coverage()

        # Calculate overall statistics
        total_drugs = self.session.query(Drug).count()
        formulary_drugs = self.session.query(Drug).filter(
            Drug.formulary_status == "FORMULARY"
        ).count()

        report = {
            "summary": {
                "total_drugs": total_drugs,
                "formulary_drugs": formulary_drugs,
                "total_gaps_identified": len(gaps),
                "critical_gaps": sum(1 for g in gaps if g.severity == GapSeverity.CRITICAL.value),
                "high_priority_gaps": sum(1 for g in gaps if g.severity == GapSeverity.HIGH.value),
                "average_who_coverage": round(
                    sum(heatmap_data["coverage"]) / len(heatmap_data["coverage"]), 2
                ) if heatmap_data["coverage"] else 0
            },
            "gaps_by_severity": {
                "critical": [g for g in gaps if g.severity == GapSeverity.CRITICAL.value],
                "high": [g for g in gaps if g.severity == GapSeverity.HIGH.value],
                "medium": [g for g in gaps if g.severity == GapSeverity.MEDIUM.value],
                "low": [g for g in gaps if g.severity == GapSeverity.LOW.value]
            },
            "coverage_heatmap": heatmap_data,
            "atc_coverage": atc_coverage,
            "recommendations": self._generate_recommendations(gaps)
        }

        return report

    def _generate_recommendations(self, gaps: List[Gap]) -> List[str]:
        """Generate high-level recommendations based on gaps."""
        recommendations = []

        critical_gaps = [g for g in gaps if g.severity == GapSeverity.CRITICAL.value]
        if critical_gaps:
            recommendations.append(
                f"URGENT: Address {len(critical_gaps)} critical gap(s) immediately. "
                "These represent essential medicines or critical therapeutic areas."
            )

        high_gaps = [g for g in gaps if g.severity == GapSeverity.HIGH.value]
        if high_gaps:
            recommendations.append(
                f"HIGH PRIORITY: Plan for addressing {len(high_gaps)} high-priority gap(s) "
                "within the next formulary review cycle."
            )

        # Check for specific patterns
        low_coverage_areas = [g.therapeutic_area for g in gaps if g.gap_type == GapType.LOW_COVERAGE.value]
        if low_coverage_areas:
            recommendations.append(
                f"Consider comprehensive review of: {', '.join(set(low_coverage_areas))}"
            )

        return recommendations
