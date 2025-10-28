"""
Expiry date tracking and wastage prevention system.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pharmintel.core.models import Drug, DrugBatch
from pharmintel.config import (
    EXPIRY_ALERT_CRITICAL,
    EXPIRY_ALERT_WARNING,
    EXPIRY_ALERT_INFO
)

logger = logging.getLogger(__name__)


class ExpiryAlert Level(Enum):
    """Expiry alert severity levels."""
    CRITICAL = "critical"  # < 30 days
    WARNING = "warning"    # 30-60 days
    INFO = "info"          # 60-90 days
    NORMAL = "normal"      # > 90 days


class UsageVelocity(Enum):
    """Drug usage velocity classifications."""
    VERY_FAST = "very_fast"  # Will be used quickly
    FAST = "fast"
    MODERATE = "moderate"
    SLOW = "slow"
    VERY_SLOW = "very_slow"  # Risk of expiry


@dataclass
class ExpiryAlert:
    """Expiry alert data structure."""
    batch_id: int
    drug_id: int
    drug_name: str
    material_number: str
    batch_number: str
    expiry_date: date
    days_until_expiry: int
    quantity: float
    alert_level: str
    recommendation: str
    estimated_wastage_risk: str


@dataclass
class UsagePattern:
    """Drug usage pattern analysis."""
    drug_id: int
    drug_name: str
    average_daily_usage: float
    usage_velocity: str
    current_stock: float
    days_until_depletion: Optional[int]
    reorder_recommended: bool


class ExpiryTracker:
    """Tracks drug expiry dates and provides wastage prevention recommendations."""

    def __init__(self, session: Session):
        """
        Initialize expiry tracker.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.today = date.today()

    def get_all_expiring_batches(
        self,
        days_threshold: int = EXPIRY_ALERT_INFO
    ) -> List[ExpiryAlert]:
        """
        Get all batches expiring within threshold.

        Args:
            days_threshold: Number of days to look ahead (default: 90)

        Returns:
            List of ExpiryAlert objects
        """
        threshold_date = self.today + timedelta(days=days_threshold)

        batches = self.session.query(DrugBatch).join(Drug).filter(
            and_(
                DrugBatch.expiry_date <= threshold_date,
                DrugBatch.expiry_date >= self.today,
                DrugBatch.quantity > 0
            )
        ).all()

        alerts = []
        for batch in batches:
            days_until_expiry = (batch.expiry_date - self.today).days
            alert = self._create_expiry_alert(batch, days_until_expiry)
            alerts.append(alert)

        # Sort by urgency (days until expiry)
        alerts.sort(key=lambda x: x.days_until_expiry)

        return alerts

    def _create_expiry_alert(self, batch: DrugBatch, days_until_expiry: int) -> ExpiryAlert:
        """Create an expiry alert from a batch."""
        alert_level = self._determine_alert_level(days_until_expiry)
        recommendation = self._generate_recommendation(batch, days_until_expiry, alert_level)
        wastage_risk = self._assess_wastage_risk(batch, days_until_expiry)

        return ExpiryAlert(
            batch_id=batch.id,
            drug_id=batch.drug_id,
            drug_name=batch.drug.material,
            material_number=batch.drug.material_number,
            batch_number=batch.batch_number,
            expiry_date=batch.expiry_date,
            days_until_expiry=days_until_expiry,
            quantity=batch.quantity,
            alert_level=alert_level,
            recommendation=recommendation,
            estimated_wastage_risk=wastage_risk
        )

    def _determine_alert_level(self, days_until_expiry: int) -> str:
        """Determine alert level based on days until expiry."""
        if days_until_expiry <= EXPIRY_ALERT_CRITICAL:
            return ExpiryAlertLevel.CRITICAL.value
        elif days_until_expiry <= EXPIRY_ALERT_WARNING:
            return ExpiryAlertLevel.WARNING.value
        elif days_until_expiry <= EXPIRY_ALERT_INFO:
            return ExpiryAlertLevel.INFO.value
        else:
            return ExpiryAlertLevel.NORMAL.value

    def _generate_recommendation(
        self,
        batch: DrugBatch,
        days_until_expiry: int,
        alert_level: str
    ) -> str:
        """Generate recommendation for expiring batch."""
        if alert_level == ExpiryAlertLevel.CRITICAL.value:
            return (
                f"URGENT: Use immediately or consider donation/transfer. "
                f"Only {days_until_expiry} days remaining."
            )
        elif alert_level == ExpiryAlertLevel.WARNING.value:
            return (
                f"Prioritize usage. Consider inter-hospital lending if excess stock. "
                f"{days_until_expiry} days remaining."
            )
        elif alert_level == ExpiryAlertLevel.INFO.value:
            return (
                f"Monitor usage. Plan consumption over next {days_until_expiry} days. "
                f"Update reorder schedule if needed."
            )
        else:
            return "Normal monitoring. No immediate action required."

    def _assess_wastage_risk(self, batch: DrugBatch, days_until_expiry: int) -> str:
        """Assess risk of wastage for a batch."""
        # Simple heuristic based on quantity and days remaining
        daily_target_usage = batch.quantity / max(days_until_expiry, 1)

        if days_until_expiry <= 7:
            return "Very High"
        elif days_until_expiry <= 14:
            return "High"
        elif days_until_expiry <= 30:
            return "Moderate"
        elif days_until_expiry <= 60:
            return "Low"
        else:
            return "Very Low"

    def get_critical_alerts(self) -> List[ExpiryAlert]:
        """Get only critical expiry alerts (< 30 days)."""
        all_alerts = self.get_all_expiring_batches(EXPIRY_ALERT_CRITICAL)
        return [a for a in all_alerts if a.alert_level == ExpiryAlertLevel.CRITICAL.value]

    def get_alerts_by_therapeutic_area(self, therapeutic_area: str) -> List[ExpiryAlert]:
        """
        Get expiry alerts for specific therapeutic area.

        Args:
            therapeutic_area: Name of therapeutic area

        Returns:
            List of alerts for that area
        """
        all_alerts = self.get_all_expiring_batches()

        # Filter by therapeutic area
        filtered_alerts = []
        for alert in all_alerts:
            drug = self.session.query(Drug).get(alert.drug_id)
            if drug and drug.therapeutic_area and drug.therapeutic_area.value == therapeutic_area:
                filtered_alerts.append(alert)

        return filtered_alerts

    def calculate_wastage_statistics(self) -> Dict:
        """
        Calculate wastage statistics and projections.

        Returns:
            Dictionary with wastage statistics
        """
        alerts = self.get_all_expiring_batches()

        stats = {
            "total_batches_expiring": len(alerts),
            "critical_batches": sum(1 for a in alerts if a.alert_level == ExpiryAlertLevel.CRITICAL.value),
            "warning_batches": sum(1 for a in alerts if a.alert_level == ExpiryAlertLevel.WARNING.value),
            "info_batches": sum(1 for a in alerts if a.alert_level == ExpiryAlertLevel.INFO.value),
            "total_quantity_at_risk": sum(a.quantity for a in alerts),
            "high_risk_quantity": sum(
                a.quantity for a in alerts
                if a.estimated_wastage_risk in ["Very High", "High"]
            ),
            "by_therapeutic_area": {},
            "top_wastage_risks": []
        }

        # Group by therapeutic area
        for alert in alerts:
            drug = self.session.query(Drug).get(alert.drug_id)
            if drug and drug.therapeutic_area:
                area = drug.therapeutic_area.value
                if area not in stats["by_therapeutic_area"]:
                    stats["by_therapeutic_area"][area] = {
                        "count": 0,
                        "quantity": 0
                    }
                stats["by_therapeutic_area"][area]["count"] += 1
                stats["by_therapeutic_area"][area]["quantity"] += alert.quantity

        # Top wastage risks
        high_risk_alerts = [a for a in alerts if a.estimated_wastage_risk in ["Very High", "High"]]
        stats["top_wastage_risks"] = sorted(
            high_risk_alerts,
            key=lambda x: x.quantity,
            reverse=True
        )[:10]

        return stats

    def update_batch_priorities(self):
        """Update priority levels for all batches based on expiry dates."""
        batches = self.session.query(DrugBatch).all()
        updated_count = 0

        for batch in batches:
            days_until_expiry = (batch.expiry_date - self.today).days

            # Set priority (0-10, higher = more urgent)
            if days_until_expiry < 0:
                batch.is_expired = True
                batch.priority_level = 10
            elif days_until_expiry <= 7:
                batch.is_near_expiry = True
                batch.priority_level = 9
            elif days_until_expiry <= 14:
                batch.is_near_expiry = True
                batch.priority_level = 8
            elif days_until_expiry <= 30:
                batch.is_near_expiry = True
                batch.priority_level = 7
            elif days_until_expiry <= 60:
                batch.is_near_expiry = True
                batch.priority_level = 5
            elif days_until_expiry <= 90:
                batch.priority_level = 3
            else:
                batch.priority_level = 1

            updated_count += 1

        self.session.commit()
        logger.info(f"Updated priorities for {updated_count} batches")

    def get_expiring_drugs_for_lending(self, min_days: int = 14, max_days: int = 60) -> List[Dict]:
        """
        Get drugs suitable for inter-hospital lending (expiring soon but not critically).

        Args:
            min_days: Minimum days until expiry
            max_days: Maximum days until expiry

        Returns:
            List of drugs suitable for lending
        """
        min_date = self.today + timedelta(days=min_days)
        max_date = self.today + timedelta(days=max_days)

        batches = self.session.query(DrugBatch).join(Drug).filter(
            and_(
                DrugBatch.expiry_date >= min_date,
                DrugBatch.expiry_date <= max_date,
                DrugBatch.quantity > 0
            )
        ).all()

        lending_candidates = []
        for batch in batches:
            days_until_expiry = (batch.expiry_date - self.today).days

            lending_candidates.append({
                "drug_id": batch.drug_id,
                "drug_name": batch.drug.material,
                "material_number": batch.drug.material_number,
                "batch_number": batch.batch_number,
                "quantity_available": batch.quantity,
                "expiry_date": batch.expiry_date,
                "days_until_expiry": days_until_expiry,
                "therapeutic_area": batch.drug.therapeutic_area.value if batch.drug.therapeutic_area else None
            })

        return lending_candidates

    def generate_expiry_report(self) -> Dict:
        """
        Generate comprehensive expiry tracking report.

        Returns:
            Dictionary with complete expiry analysis
        """
        alerts = self.get_all_expiring_batches()
        wastage_stats = self.calculate_wastage_statistics()
        lending_candidates = self.get_expiring_drugs_for_lending()

        report = {
            "report_date": self.today.isoformat(),
            "summary": {
                "total_alerts": len(alerts),
                "critical_alerts": wastage_stats["critical_batches"],
                "warning_alerts": wastage_stats["warning_batches"],
                "info_alerts": wastage_stats["info_batches"]
            },
            "wastage_statistics": wastage_stats,
            "critical_alerts": [a for a in alerts if a.alert_level == ExpiryAlertLevel.CRITICAL.value],
            "lending_opportunities": len(lending_candidates),
            "recommendations": self._generate_report_recommendations(alerts, wastage_stats)
        }

        return report

    def _generate_report_recommendations(
        self,
        alerts: List[ExpiryAlert],
        wastage_stats: Dict
    ) -> List[str]:
        """Generate high-level recommendations for expiry management."""
        recommendations = []

        if wastage_stats["critical_batches"] > 0:
            recommendations.append(
                f"URGENT: {wastage_stats['critical_batches']} batch(es) expiring within 30 days. "
                "Immediate action required to prevent wastage."
            )

        if wastage_stats["high_risk_quantity"] > 100:
            recommendations.append(
                f"High wastage risk: {wastage_stats['high_risk_quantity']:.0f} units at risk. "
                "Consider inter-hospital lending or donation."
            )

        # Check for problematic areas
        for area, data in wastage_stats.get("by_therapeutic_area", {}).items():
            if data["count"] >= 5:
                recommendations.append(
                    f"{area}: {data['count']} batches expiring. Review inventory levels and ordering patterns."
                )

        if not recommendations:
            recommendations.append("Expiry management is under control. Continue routine monitoring.")

        return recommendations
