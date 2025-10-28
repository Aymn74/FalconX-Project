"""
Non-formulary drug evaluator and usage analyzer.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pharmintel.core.models import (
    Drug, DrugUsageRecord, FormularyStatus
)
from pharmintel.config import MIN_USAGE_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class NonFormularyAnalysis:
    """Analysis result for a non-formulary drug."""
    drug_id: int
    drug_name: str
    material_number: str
    usage_count: int
    total_quantity_used: float
    unique_departments: int
    common_indications: List[str]
    avg_monthly_usage: float
    cost_impact: Optional[float]
    promotion_score: float
    recommendation: str


class NonFormularyEvaluator:
    """Evaluates and tracks non-formulary drug usage."""

    def __init__(self, session: Session):
        """
        Initialize non-formulary evaluator.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def get_non_formulary_drugs(self) -> List[Drug]:
        """
        Get all non-formulary drugs.

        Returns:
            List of non-formulary Drug objects
        """
        return self.session.query(Drug).filter(
            Drug.formulary_status == FormularyStatus.NON_FORMULARY
        ).all()

    def analyze_non_formulary_usage(
        self,
        drug_id: int,
        lookback_days: int = 180
    ) -> Optional[NonFormularyAnalysis]:
        """
        Analyze usage patterns for a non-formulary drug.

        Args:
            drug_id: Drug ID to analyze
            lookback_days: Days to look back

        Returns:
            NonFormularyAnalysis object or None if no usage
        """
        drug = self.session.query(Drug).get(drug_id)
        if not drug or drug.formulary_status != FormularyStatus.NON_FORMULARY:
            return None

        start_date = date.today() - timedelta(days=lookback_days)

        # Get usage records
        usage_records = self.session.query(DrugUsageRecord).filter(
            and_(
                DrugUsageRecord.drug_id == drug_id,
                DrugUsageRecord.usage_date >= start_date,
                DrugUsageRecord.is_non_formulary == True
            )
        ).all()

        if not usage_records:
            return None

        # Calculate statistics
        usage_count = len(usage_records)
        total_quantity = sum(r.quantity_used for r in usage_records)

        # Unique departments
        departments = set(r.department for r in usage_records if r.department)
        unique_departments = len(departments)

        # Common indications
        indication_counts = defaultdict(int)
        for record in usage_records:
            if record.indication:
                indication_counts[record.indication] += 1

        common_indications = sorted(
            indication_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]
        common_indications = [ind[0] for ind in common_indications]

        # Average monthly usage
        months = lookback_days / 30
        avg_monthly_usage = usage_count / months if months > 0 else 0

        # Cost impact
        cost_impact = None
        if drug.cost_per_unit:
            cost_impact = total_quantity * drug.cost_per_unit

        # Calculate promotion score (0-10)
        promotion_score = self._calculate_promotion_score(
            usage_count=usage_count,
            avg_monthly_usage=avg_monthly_usage,
            unique_departments=unique_departments,
            lookback_days=lookback_days
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            promotion_score=promotion_score,
            usage_count=usage_count,
            avg_monthly_usage=avg_monthly_usage
        )

        return NonFormularyAnalysis(
            drug_id=drug_id,
            drug_name=drug.material,
            material_number=drug.material_number,
            usage_count=usage_count,
            total_quantity_used=total_quantity,
            unique_departments=unique_departments,
            common_indications=common_indications,
            avg_monthly_usage=round(avg_monthly_usage, 2),
            cost_impact=cost_impact,
            promotion_score=promotion_score,
            recommendation=recommendation
        )

    def _calculate_promotion_score(
        self,
        usage_count: int,
        avg_monthly_usage: float,
        unique_departments: int,
        lookback_days: int
    ) -> float:
        """
        Calculate score for promoting drug to formulary (0-10).

        Args:
            usage_count: Total usage count
            avg_monthly_usage: Average monthly usage
            unique_departments: Number of departments using it
            lookback_days: Analysis period

        Returns:
            Score between 0 and 10
        """
        score = 0.0

        # Usage frequency component (0-4 points)
        if avg_monthly_usage >= 10:
            score += 4
        elif avg_monthly_usage >= 5:
            score += 3
        elif avg_monthly_usage >= 2:
            score += 2
        elif avg_monthly_usage >= 1:
            score += 1

        # Consistency component (0-3 points)
        # High usage count suggests consistent need
        if usage_count >= 50:
            score += 3
        elif usage_count >= 25:
            score += 2
        elif usage_count >= 10:
            score += 1

        # Department diversity (0-3 points)
        # Multiple departments suggests broad utility
        if unique_departments >= 5:
            score += 3
        elif unique_departments >= 3:
            score += 2
        elif unique_departments >= 2:
            score += 1

        return round(score, 1)

    def _generate_recommendation(
        self,
        promotion_score: float,
        usage_count: int,
        avg_monthly_usage: float
    ) -> str:
        """Generate recommendation based on analysis."""
        if promotion_score >= 7:
            return (
                "STRONG CANDIDATE for formulary promotion. "
                "High usage frequency across multiple departments. "
                "Review clinical evidence and cost-effectiveness."
            )
        elif promotion_score >= 5:
            return (
                "CONSIDER for formulary promotion. "
                "Moderate consistent usage. Evaluate clinical justification "
                "and potential for therapeutic interchange."
            )
        elif promotion_score >= 3:
            return (
                "MONITOR usage trends. "
                "Usage is moderate but may not justify formulary addition yet. "
                "Continue tracking for another review period."
            )
        else:
            return (
                "LOW PRIORITY for formulary addition. "
                "Usage is sporadic or low. Maintain non-formulary status "
                "with exception approval process."
            )

    def identify_promotion_candidates(
        self,
        min_score: float = 5.0,
        lookback_days: int = 180
    ) -> List[NonFormularyAnalysis]:
        """
        Identify non-formulary drugs that are candidates for promotion.

        Args:
            min_score: Minimum promotion score required
            lookback_days: Days to analyze

        Returns:
            List of candidate drugs sorted by score
        """
        non_formulary_drugs = self.get_non_formulary_drugs()
        candidates = []

        for drug in non_formulary_drugs:
            analysis = self.analyze_non_formulary_usage(drug.id, lookback_days)

            if analysis and analysis.promotion_score >= min_score:
                candidates.append(analysis)

        # Sort by promotion score (descending)
        candidates.sort(key=lambda x: x.promotion_score, reverse=True)

        return candidates

    def calculate_cost_impact(self, lookback_days: int = 365) -> Dict:
        """
        Calculate total cost impact of non-formulary drug usage.

        Args:
            lookback_days: Days to analyze

        Returns:
            Dictionary with cost analysis
        """
        start_date = date.today() - timedelta(days=lookback_days)

        # Get all non-formulary usage
        non_formulary_drugs = self.get_non_formulary_drugs()

        total_cost = 0
        by_drug = []
        by_therapeutic_area = defaultdict(float)

        for drug in non_formulary_drugs:
            if not drug.cost_per_unit:
                continue

            usage = self.session.query(
                func.sum(DrugUsageRecord.quantity_used)
            ).filter(
                and_(
                    DrugUsageRecord.drug_id == drug.id,
                    DrugUsageRecord.usage_date >= start_date,
                    DrugUsageRecord.is_non_formulary == True
                )
            ).scalar() or 0

            drug_cost = usage * drug.cost_per_unit

            if drug_cost > 0:
                total_cost += drug_cost

                by_drug.append({
                    "drug_name": drug.material,
                    "material_number": drug.material_number,
                    "quantity_used": usage,
                    "cost_per_unit": drug.cost_per_unit,
                    "total_cost": round(drug_cost, 2)
                })

                if drug.therapeutic_area:
                    by_therapeutic_area[drug.therapeutic_area.value] += drug_cost

        # Sort by cost
        by_drug.sort(key=lambda x: x["total_cost"], reverse=True)

        return {
            "analysis_period_days": lookback_days,
            "total_cost": round(total_cost, 2),
            "drug_count": len(by_drug),
            "top_10_drugs": by_drug[:10],
            "by_therapeutic_area": dict(by_therapeutic_area),
            "average_cost_per_drug": round(total_cost / len(by_drug), 2) if by_drug else 0
        }

    def track_exception_requests(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """
        Track non-formulary exception requests.

        Args:
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Dictionary with exception request statistics
        """
        if not end_date:
            end_date = date.today()

        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Get usage records with justifications (exception requests)
        exceptions = self.session.query(DrugUsageRecord).filter(
            and_(
                DrugUsageRecord.is_non_formulary == True,
                DrugUsageRecord.usage_date >= start_date,
                DrugUsageRecord.usage_date <= end_date,
                DrugUsageRecord.justification.isnot(None)
            )
        ).all()

        # Analyze
        by_drug = defaultdict(lambda: {
            "count": 0,
            "justifications": []
        })

        by_approver = defaultdict(int)

        for exc in exceptions:
            drug_name = exc.drug.material
            by_drug[drug_name]["count"] += 1

            if exc.justification:
                by_drug[drug_name]["justifications"].append(exc.justification)

            if exc.approved_by:
                by_approver[exc.approved_by] += 1

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_exceptions": len(exceptions),
            "unique_drugs": len(by_drug),
            "by_drug": dict(by_drug),
            "by_approver": dict(by_approver),
            "most_requested": sorted(
                by_drug.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:10]
        }

    def generate_comprehensive_report(self, lookback_days: int = 180) -> Dict:
        """
        Generate comprehensive non-formulary analysis report.

        Args:
            lookback_days: Days to analyze

        Returns:
            Dictionary with complete analysis
        """
        logger.info("Generating non-formulary analysis report...")

        non_formulary_drugs = self.get_non_formulary_drugs()
        promotion_candidates = self.identify_promotion_candidates(
            min_score=5.0,
            lookback_days=lookback_days
        )
        cost_impact = self.calculate_cost_impact(lookback_days)
        exception_tracking = self.track_exception_requests()

        # Analyze all non-formulary drugs
        all_analyses = []
        for drug in non_formulary_drugs:
            analysis = self.analyze_non_formulary_usage(drug.id, lookback_days)
            if analysis:
                all_analyses.append(analysis)

        report = {
            "report_date": date.today().isoformat(),
            "analysis_period_days": lookback_days,
            "summary": {
                "total_non_formulary_drugs": len(non_formulary_drugs),
                "drugs_with_usage": len(all_analyses),
                "promotion_candidates": len(promotion_candidates),
                "total_cost_impact": cost_impact["total_cost"],
                "exception_requests": exception_tracking["total_exceptions"]
            },
            "promotion_candidates": [
                {
                    "drug_name": c.drug_name,
                    "material_number": c.material_number,
                    "promotion_score": c.promotion_score,
                    "usage_count": c.usage_count,
                    "avg_monthly_usage": c.avg_monthly_usage,
                    "unique_departments": c.unique_departments,
                    "recommendation": c.recommendation
                }
                for c in promotion_candidates[:10]
            ],
            "cost_impact": cost_impact,
            "exception_tracking": exception_tracking,
            "usage_distribution": {
                "high_usage": sum(1 for a in all_analyses if a.avg_monthly_usage >= 5),
                "moderate_usage": sum(1 for a in all_analyses if 1 <= a.avg_monthly_usage < 5),
                "low_usage": sum(1 for a in all_analyses if a.avg_monthly_usage < 1)
            },
            "recommendations": self._generate_report_recommendations(
                promotion_candidates,
                all_analyses,
                cost_impact
            )
        }

        return report

    def _generate_report_recommendations(
        self,
        promotion_candidates: List[NonFormularyAnalysis],
        all_analyses: List[NonFormularyAnalysis],
        cost_impact: Dict
    ) -> List[str]:
        """Generate high-level recommendations."""
        recommendations = []

        if len(promotion_candidates) > 0:
            recommendations.append(
                f"Review {len(promotion_candidates)} drug(s) for potential formulary promotion. "
                "These drugs show consistent high usage patterns."
            )

        if cost_impact["total_cost"] > 100000:
            recommendations.append(
                f"Non-formulary costs total ${cost_impact['total_cost']:,.2f}. "
                "Consider formulary optimization to reduce costs through competitive bidding."
            )

        high_cost_drugs = [d for d in cost_impact.get("top_10_drugs", []) if d["total_cost"] > 10000]
        if high_cost_drugs:
            recommendations.append(
                f"{len(high_cost_drugs)} non-formulary drug(s) have significant cost impact. "
                "Evaluate for therapeutic alternatives or formulary addition."
            )

        if not recommendations:
            recommendations.append(
                "Non-formulary usage is within acceptable parameters. Continue monitoring."
            )

        return recommendations
