"""
Inventory intelligence with AI-based usage prediction.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import statistics

from sqlalchemy.orm import Session
from sqlalchemy import func
from pharmintel.core.models import Drug, DrugBatch, DrugUsageRecord
from pharmintel.config import LOW_STOCK_THRESHOLD, REORDER_MULTIPLIER

logger = logging.getLogger(__name__)


@dataclass
class StockAlert:
    """Stock level alert."""
    drug_id: int
    drug_name: str
    material_number: str
    current_stock: float
    reorder_point: float
    days_until_stockout: Optional[int]
    recommended_order_quantity: float
    alert_level: str


@dataclass
class UsagePrediction:
    """Usage prediction for a drug."""
    drug_id: int
    drug_name: str
    historical_daily_average: float
    predicted_daily_usage: float
    trend: str  # increasing, decreasing, stable
    confidence: str  # high, medium, low
    prediction_basis: str


class InventoryManager:
    """Manages inventory intelligence and predictions."""

    def __init__(self, session: Session):
        """
        Initialize inventory manager.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def analyze_usage_patterns(
        self,
        drug_id: int,
        lookback_days: int = 90
    ) -> Optional[UsagePrediction]:
        """
        Analyze usage patterns for a drug.

        Args:
            drug_id: Drug ID to analyze
            lookback_days: Number of days to look back

        Returns:
            UsagePrediction object or None if insufficient data
        """
        drug = self.session.query(Drug).get(drug_id)
        if not drug:
            return None

        start_date = date.today() - timedelta(days=lookback_days)

        # Get usage records
        usage_records = self.session.query(DrugUsageRecord).filter(
            DrugUsageRecord.drug_id == drug_id,
            DrugUsageRecord.usage_date >= start_date
        ).order_by(DrugUsageRecord.usage_date).all()

        if len(usage_records) < 5:
            # Insufficient data
            return None

        # Calculate daily averages
        daily_totals = defaultdict(float)
        for record in usage_records:
            daily_totals[record.usage_date] += record.quantity_used

        daily_values = list(daily_totals.values())
        historical_avg = statistics.mean(daily_values) if daily_values else 0

        # Detect trend
        if len(daily_values) >= 14:
            first_half = daily_values[:len(daily_values)//2]
            second_half = daily_values[len(daily_values)//2:]

            avg_first = statistics.mean(first_half)
            avg_second = statistics.mean(second_half)

            if avg_second > avg_first * 1.2:
                trend = "increasing"
                predicted_daily = avg_second * 1.1  # Account for trend
            elif avg_second < avg_first * 0.8:
                trend = "decreasing"
                predicted_daily = avg_second * 0.9
            else:
                trend = "stable"
                predicted_daily = historical_avg
        else:
            trend = "stable"
            predicted_daily = historical_avg

        # Determine confidence based on data consistency
        if daily_values:
            std_dev = statistics.stdev(daily_values) if len(daily_values) > 1 else 0
            cv = (std_dev / historical_avg) if historical_avg > 0 else 0

            if cv < 0.3:
                confidence = "high"
            elif cv < 0.6:
                confidence = "medium"
            else:
                confidence = "low"
        else:
            confidence = "low"

        return UsagePrediction(
            drug_id=drug_id,
            drug_name=drug.material,
            historical_daily_average=round(historical_avg, 2),
            predicted_daily_usage=round(predicted_daily, 2),
            trend=trend,
            confidence=confidence,
            prediction_basis=f"{len(usage_records)} records over {lookback_days} days"
        )

    def check_stock_levels(self) -> List[StockAlert]:
        """
        Check stock levels for all drugs and generate alerts.

        Returns:
            List of stock alerts
        """
        alerts = []
        drugs = self.session.query(Drug).filter(
            Drug.current_stock_level.isnot(None)
        ).all()

        for drug in drugs:
            # Analyze usage
            prediction = self.analyze_usage_patterns(drug.id)

            # Determine reorder point if not set
            reorder_point = drug.reorder_point
            if not reorder_point and prediction:
                # Estimate reorder point as 7 days of predicted usage
                reorder_point = prediction.predicted_daily_usage * 7

            # Check if below reorder point
            if reorder_point and drug.current_stock_level <= reorder_point:
                # Calculate days until stockout
                days_until_stockout = None
                if prediction and prediction.predicted_daily_usage > 0:
                    days_until_stockout = int(drug.current_stock_level / prediction.predicted_daily_usage)

                # Calculate recommended order quantity
                if prediction:
                    # Order for 30 days with safety factor
                    recommended_qty = prediction.predicted_daily_usage * 30 * REORDER_MULTIPLIER
                else:
                    # Fallback to reorder point * multiplier
                    recommended_qty = reorder_point * REORDER_MULTIPLIER

                # Determine alert level
                if drug.current_stock_level <= LOW_STOCK_THRESHOLD:
                    alert_level = "critical"
                elif days_until_stockout and days_until_stockout <= 7:
                    alert_level = "urgent"
                elif drug.current_stock_level <= reorder_point * 0.5:
                    alert_level = "warning"
                else:
                    alert_level = "info"

                alert = StockAlert(
                    drug_id=drug.id,
                    drug_name=drug.material,
                    material_number=drug.material_number,
                    current_stock=drug.current_stock_level,
                    reorder_point=reorder_point,
                    days_until_stockout=days_until_stockout,
                    recommended_order_quantity=round(recommended_qty, 2),
                    alert_level=alert_level
                )
                alerts.append(alert)

        # Sort by urgency
        priority_order = {"critical": 0, "urgent": 1, "warning": 2, "info": 3}
        alerts.sort(key=lambda x: (priority_order.get(x.alert_level, 4), x.days_until_stockout or 999))

        return alerts

    def optimize_reorder_points(self):
        """
        Optimize reorder points for all drugs based on usage patterns.
        """
        drugs = self.session.query(Drug).all()
        updated_count = 0

        for drug in drugs:
            prediction = self.analyze_usage_patterns(drug.id)

            if prediction and prediction.confidence in ["high", "medium"]:
                # Calculate optimal reorder point
                # Use 14 days of predicted usage as safety stock
                optimal_reorder = prediction.predicted_daily_usage * 14

                # Update if different from current
                if drug.reorder_point != optimal_reorder:
                    drug.reorder_point = optimal_reorder
                    updated_count += 1

        self.session.commit()
        logger.info(f"Optimized reorder points for {updated_count} drugs")

    def predict_next_month_requirements(self) -> Dict[int, float]:
        """
        Predict inventory requirements for next month.

        Returns:
            Dictionary mapping drug_id to predicted quantity needed
        """
        predictions = {}
        drugs = self.session.query(Drug).all()

        for drug in drugs:
            prediction = self.analyze_usage_patterns(drug.id)

            if prediction:
                # Predict for 30 days
                monthly_requirement = prediction.predicted_daily_usage * 30
                predictions[drug.id] = round(monthly_requirement, 2)

        return predictions

    def identify_slow_moving_items(self, threshold_days: int = 90) -> List[Dict]:
        """
        Identify slow-moving inventory items.

        Args:
            threshold_days: Days to look back for usage

        Returns:
            List of slow-moving items
        """
        slow_moving = []
        drugs = self.session.query(Drug).filter(
            Drug.current_stock_level > 0
        ).all()

        start_date = date.today() - timedelta(days=threshold_days)

        for drug in drugs:
            # Check usage in period
            usage_count = self.session.query(func.count(DrugUsageRecord.id)).filter(
                DrugUsageRecord.drug_id == drug.id,
                DrugUsageRecord.usage_date >= start_date
            ).scalar()

            total_usage = self.session.query(func.sum(DrugUsageRecord.quantity_used)).filter(
                DrugUsageRecord.drug_id == drug.id,
                DrugUsageRecord.usage_date >= start_date
            ).scalar() or 0

            # If low usage and has stock
            if usage_count < 3 and drug.current_stock_level > 0:
                slow_moving.append({
                    "drug_id": drug.id,
                    "drug_name": drug.material,
                    "material_number": drug.material_number,
                    "current_stock": drug.current_stock_level,
                    "usage_count": usage_count,
                    "total_usage": total_usage,
                    "days_analyzed": threshold_days,
                    "recommendation": "Consider reducing order quantities or lending to other facilities"
                })

        return slow_moving

    def generate_inventory_report(self) -> Dict:
        """
        Generate comprehensive inventory intelligence report.

        Returns:
            Dictionary with inventory analysis
        """
        stock_alerts = self.check_stock_levels()
        slow_moving = self.identify_slow_moving_items()
        next_month_predictions = self.predict_next_month_requirements()

        # Calculate statistics
        total_drugs = self.session.query(Drug).count()
        drugs_in_stock = self.session.query(Drug).filter(
            Drug.current_stock_level > 0
        ).count()

        total_value = self.session.query(
            func.sum(Drug.current_stock_level * Drug.cost_per_unit)
        ).filter(
            Drug.cost_per_unit.isnot(None),
            Drug.current_stock_level.isnot(None)
        ).scalar() or 0

        report = {
            "report_date": date.today().isoformat(),
            "summary": {
                "total_drugs": total_drugs,
                "drugs_in_stock": drugs_in_stock,
                "stock_out_count": total_drugs - drugs_in_stock,
                "total_inventory_value": round(total_value, 2),
                "critical_alerts": sum(1 for a in stock_alerts if a.alert_level == "critical"),
                "urgent_alerts": sum(1 for a in stock_alerts if a.alert_level == "urgent"),
                "slow_moving_items": len(slow_moving)
            },
            "stock_alerts": [
                {
                    "drug_name": a.drug_name,
                    "material_number": a.material_number,
                    "current_stock": a.current_stock,
                    "reorder_point": a.reorder_point,
                    "days_until_stockout": a.days_until_stockout,
                    "recommended_order": a.recommended_order_quantity,
                    "alert_level": a.alert_level
                }
                for a in stock_alerts[:20]  # Top 20 alerts
            ],
            "slow_moving_items": slow_moving[:10],  # Top 10
            "next_month_top_requirements": sorted(
                [
                    {"drug_id": k, "predicted_quantity": v}
                    for k, v in next_month_predictions.items()
                ],
                key=lambda x: x["predicted_quantity"],
                reverse=True
            )[:10],
            "recommendations": self._generate_inventory_recommendations(stock_alerts, slow_moving)
        }

        return report

    def _generate_inventory_recommendations(
        self,
        stock_alerts: List[StockAlert],
        slow_moving: List[Dict]
    ) -> List[str]:
        """Generate inventory management recommendations."""
        recommendations = []

        critical_alerts = [a for a in stock_alerts if a.alert_level == "critical"]
        if critical_alerts:
            recommendations.append(
                f"CRITICAL: {len(critical_alerts)} drug(s) at critically low stock. "
                "Place emergency orders immediately."
            )

        urgent_alerts = [a for a in stock_alerts if a.alert_level == "urgent"]
        if urgent_alerts:
            recommendations.append(
                f"URGENT: {len(urgent_alerts)} drug(s) will stock out within 7 days. "
                "Expedite ordering process."
            )

        if len(slow_moving) >= 5:
            recommendations.append(
                f"Review ordering patterns: {len(slow_moving)} slow-moving items identified. "
                "Consider inter-hospital lending or reduced order quantities."
            )

        if not recommendations:
            recommendations.append("Inventory levels are generally healthy. Continue monitoring.")

        return recommendations
