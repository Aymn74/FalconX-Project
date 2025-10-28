"""
Inter-hospital lending tracker and coordination system.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from pharmintel.core.models import (
    Drug, Hospital, LendingTransaction, LendingStatus
)

logger = logging.getLogger(__name__)


@dataclass
class LendingBalance:
    """Hospital lending balance summary."""
    hospital_id: int
    hospital_name: str
    total_lent: int
    total_borrowed: int
    net_balance: int  # positive = more lent than borrowed
    active_lendings: int
    active_borrowings: int


class LendingTracker:
    """Tracks and manages inter-hospital drug lending."""

    def __init__(self, session: Session):
        """
        Initialize lending tracker.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def create_lending_request(
        self,
        drug_id: int,
        from_hospital_id: int,
        to_hospital_id: int,
        quantity: float,
        request_reason: str,
        requested_by: str,
        batch_number: Optional[str] = None,
        expected_return_date: Optional[date] = None
    ) -> LendingTransaction:
        """
        Create a new lending request.

        Args:
            drug_id: Drug being requested
            from_hospital_id: Hospital lending the drug
            to_hospital_id: Hospital borrowing the drug
            quantity: Quantity requested
            request_reason: Reason for request
            requested_by: Person making request
            batch_number: Optional specific batch number
            expected_return_date: Optional expected return date

        Returns:
            Created LendingTransaction object
        """
        transaction = LendingTransaction(
            drug_id=drug_id,
            from_hospital_id=from_hospital_id,
            to_hospital_id=to_hospital_id,
            quantity=quantity,
            batch_number=batch_number,
            status=LendingStatus.REQUESTED,
            request_reason=request_reason,
            requested_by=requested_by,
            expected_return_date=expected_return_date
        )

        self.session.add(transaction)
        self.session.commit()

        logger.info(f"Created lending request: {transaction.id}")
        return transaction

    def approve_lending_request(
        self,
        transaction_id: int,
        approved_by: str,
        approval_notes: Optional[str] = None
    ) -> LendingTransaction:
        """
        Approve a lending request.

        Args:
            transaction_id: ID of transaction to approve
            approved_by: Person approving
            approval_notes: Optional approval notes

        Returns:
            Updated transaction
        """
        transaction = self.session.query(LendingTransaction).get(transaction_id)

        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")

        if transaction.status != LendingStatus.REQUESTED:
            raise ValueError(f"Transaction is not in REQUESTED status")

        transaction.status = LendingStatus.APPROVED
        transaction.approval_date = datetime.utcnow()
        transaction.approved_by = approved_by
        transaction.approval_notes = approval_notes

        self.session.commit()

        logger.info(f"Approved lending request: {transaction_id}")
        return transaction

    def mark_delivered(
        self,
        transaction_id: int,
        delivery_notes: Optional[str] = None
    ) -> LendingTransaction:
        """
        Mark a lending transaction as delivered.

        Args:
            transaction_id: ID of transaction
            delivery_notes: Optional delivery notes

        Returns:
            Updated transaction
        """
        transaction = self.session.query(LendingTransaction).get(transaction_id)

        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")

        transaction.status = LendingStatus.DELIVERED
        transaction.delivery_date = datetime.utcnow()
        transaction.delivery_notes = delivery_notes

        self.session.commit()

        logger.info(f"Marked transaction {transaction_id} as delivered")
        return transaction

    def mark_returned(self, transaction_id: int) -> LendingTransaction:
        """
        Mark a lending transaction as returned.

        Args:
            transaction_id: ID of transaction

        Returns:
            Updated transaction
        """
        transaction = self.session.query(LendingTransaction).get(transaction_id)

        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")

        transaction.status = LendingStatus.RETURNED
        transaction.return_date = datetime.utcnow()

        self.session.commit()

        logger.info(f"Marked transaction {transaction_id} as returned")
        return transaction

    def cancel_request(self, transaction_id: int) -> LendingTransaction:
        """
        Cancel a lending request.

        Args:
            transaction_id: ID of transaction to cancel

        Returns:
            Updated transaction
        """
        transaction = self.session.query(LendingTransaction).get(transaction_id)

        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")

        transaction.status = LendingStatus.CANCELLED

        self.session.commit()

        logger.info(f"Cancelled lending request: {transaction_id}")
        return transaction

    def get_pending_requests(self, hospital_id: Optional[int] = None) -> List[LendingTransaction]:
        """
        Get pending lending requests.

        Args:
            hospital_id: Optional filter by lending hospital

        Returns:
            List of pending requests
        """
        query = self.session.query(LendingTransaction).filter(
            LendingTransaction.status == LendingStatus.REQUESTED
        )

        if hospital_id:
            query = query.filter(LendingTransaction.from_hospital_id == hospital_id)

        return query.order_by(LendingTransaction.request_date).all()

    def get_active_lendings(self, hospital_id: Optional[int] = None) -> List[LendingTransaction]:
        """
        Get active (approved/in-transit/delivered) lending transactions.

        Args:
            hospital_id: Optional filter by hospital

        Returns:
            List of active transactions
        """
        query = self.session.query(LendingTransaction).filter(
            LendingTransaction.status.in_([
                LendingStatus.APPROVED,
                LendingStatus.IN_TRANSIT,
                LendingStatus.DELIVERED
            ])
        )

        if hospital_id:
            query = query.filter(
                or_(
                    LendingTransaction.from_hospital_id == hospital_id,
                    LendingTransaction.to_hospital_id == hospital_id
                )
            )

        return query.all()

    def calculate_hospital_balance(self, hospital_id: int) -> LendingBalance:
        """
        Calculate lending/borrowing balance for a hospital.

        Args:
            hospital_id: Hospital ID

        Returns:
            LendingBalance object
        """
        hospital = self.session.query(Hospital).get(hospital_id)

        if not hospital:
            raise ValueError(f"Hospital {hospital_id} not found")

        # Count completed lendings (hospital lent out)
        total_lent = self.session.query(func.count(LendingTransaction.id)).filter(
            LendingTransaction.from_hospital_id == hospital_id,
            LendingTransaction.status.in_([
                LendingStatus.DELIVERED,
                LendingStatus.RETURNED
            ])
        ).scalar() or 0

        # Count completed borrowings (hospital borrowed)
        total_borrowed = self.session.query(func.count(LendingTransaction.id)).filter(
            LendingTransaction.to_hospital_id == hospital_id,
            LendingTransaction.status.in_([
                LendingStatus.DELIVERED,
                LendingStatus.RETURNED
            ])
        ).scalar() or 0

        # Active lendings
        active_lendings = self.session.query(func.count(LendingTransaction.id)).filter(
            LendingTransaction.from_hospital_id == hospital_id,
            LendingTransaction.status.in_([
                LendingStatus.APPROVED,
                LendingStatus.IN_TRANSIT,
                LendingStatus.DELIVERED
            ])
        ).scalar() or 0

        # Active borrowings
        active_borrowings = self.session.query(func.count(LendingTransaction.id)).filter(
            LendingTransaction.to_hospital_id == hospital_id,
            LendingTransaction.status.in_([
                LendingStatus.APPROVED,
                LendingStatus.IN_TRANSIT,
                LendingStatus.DELIVERED
            ])
        ).scalar() or 0

        return LendingBalance(
            hospital_id=hospital_id,
            hospital_name=hospital.name,
            total_lent=total_lent,
            total_borrowed=total_borrowed,
            net_balance=total_lent - total_borrowed,
            active_lendings=active_lendings,
            active_borrowings=active_borrowings
        )

    def get_lending_history(
        self,
        drug_id: Optional[int] = None,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[LendingTransaction]:
        """
        Get lending history with optional filters.

        Args:
            drug_id: Optional drug filter
            hospital_id: Optional hospital filter
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            List of transactions
        """
        query = self.session.query(LendingTransaction)

        if drug_id:
            query = query.filter(LendingTransaction.drug_id == drug_id)

        if hospital_id:
            query = query.filter(
                or_(
                    LendingTransaction.from_hospital_id == hospital_id,
                    LendingTransaction.to_hospital_id == hospital_id
                )
            )

        if start_date:
            query = query.filter(LendingTransaction.request_date >= start_date)

        if end_date:
            query = query.filter(LendingTransaction.request_date <= end_date)

        return query.order_by(LendingTransaction.request_date.desc()).all()

    def find_available_drugs_in_network(
        self,
        drug_id: int,
        requesting_hospital_id: int,
        min_quantity: float
    ) -> List[Dict]:
        """
        Find which hospitals in the network have a specific drug available.

        Args:
            drug_id: Drug to search for
            requesting_hospital_id: Hospital making the request
            min_quantity: Minimum quantity needed

        Returns:
            List of hospitals with available stock
        """
        # In a real system, this would query a network-wide inventory database
        # For now, we'll return a placeholder structure

        drug = self.session.query(Drug).get(drug_id)
        if not drug:
            return []

        # Get all hospitals except requesting one
        hospitals = self.session.query(Hospital).filter(
            Hospital.id != requesting_hospital_id,
            Hospital.is_active == True
        ).all()

        available = []
        # Placeholder: in production, query each hospital's inventory
        # For demo, we'll simulate some availability

        return available

    def get_overdue_returns(self) -> List[Dict]:
        """
        Get lendings that are overdue for return.

        Returns:
            List of overdue transactions
        """
        today = date.today()

        transactions = self.session.query(LendingTransaction).filter(
            LendingTransaction.status == LendingStatus.DELIVERED,
            LendingTransaction.expected_return_date.isnot(None),
            LendingTransaction.expected_return_date < today
        ).all()

        overdue = []
        for trans in transactions:
            days_overdue = (today - trans.expected_return_date).days

            overdue.append({
                "transaction_id": trans.id,
                "drug_name": trans.drug.material,
                "from_hospital": trans.from_hospital.name,
                "to_hospital": trans.to_hospital.name,
                "quantity": trans.quantity,
                "expected_return": trans.expected_return_date,
                "days_overdue": days_overdue,
                "delivery_date": trans.delivery_date
            })

        return overdue

    def generate_lending_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """
        Generate comprehensive lending activity report.

        Args:
            start_date: Optional start date (default: 90 days ago)
            end_date: Optional end date (default: today)

        Returns:
            Dictionary with lending statistics
        """
        if not end_date:
            end_date = date.today()

        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Get transactions in period
        transactions = self.get_lending_history(
            start_date=start_date,
            end_date=end_date
        )

        # Calculate statistics
        total_transactions = len(transactions)
        by_status = {}
        by_drug = {}
        by_hospital = {}

        for trans in transactions:
            # By status
            status = trans.status.value
            by_status[status] = by_status.get(status, 0) + 1

            # By drug
            drug_name = trans.drug.material
            if drug_name not in by_drug:
                by_drug[drug_name] = {
                    "count": 0,
                    "total_quantity": 0
                }
            by_drug[drug_name]["count"] += 1
            by_drug[drug_name]["total_quantity"] += trans.quantity

            # By hospital (lending)
            from_hosp = trans.from_hospital.name
            if from_hosp not in by_hospital:
                by_hospital[from_hosp] = {
                    "lent": 0,
                    "borrowed": 0
                }
            by_hospital[from_hosp]["lent"] += 1

            # By hospital (borrowing)
            to_hosp = trans.to_hospital.name
            if to_hosp not in by_hospital:
                by_hospital[to_hosp] = {
                    "lent": 0,
                    "borrowed": 0
                }
            by_hospital[to_hosp]["borrowed"] += 1

        # Get all hospital balances
        hospitals = self.session.query(Hospital).filter(Hospital.is_active == True).all()
        hospital_balances = [
            {
                "hospital_name": h.name,
                "total_lent": self.calculate_hospital_balance(h.id).total_lent,
                "total_borrowed": self.calculate_hospital_balance(h.id).total_borrowed,
                "net_balance": self.calculate_hospital_balance(h.id).net_balance
            }
            for h in hospitals
        ]

        # Overdue returns
        overdue = self.get_overdue_returns()

        report = {
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "summary": {
                "total_transactions": total_transactions,
                "active_lendings": sum(1 for t in transactions if t.status in [
                    LendingStatus.APPROVED,
                    LendingStatus.IN_TRANSIT,
                    LendingStatus.DELIVERED
                ]),
                "completed_lendings": sum(1 for t in transactions if t.status == LendingStatus.RETURNED),
                "pending_requests": sum(1 for t in transactions if t.status == LendingStatus.REQUESTED),
                "overdue_returns": len(overdue)
            },
            "by_status": by_status,
            "top_drugs": sorted(
                by_drug.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:10],
            "hospital_activity": by_hospital,
            "hospital_balances": sorted(
                hospital_balances,
                key=lambda x: abs(x["net_balance"]),
                reverse=True
            ),
            "overdue_returns": overdue,
            "recommendations": self._generate_lending_recommendations(overdue, hospital_balances)
        }

        return report

    def _generate_lending_recommendations(
        self,
        overdue: List[Dict],
        hospital_balances: List[Dict]
    ) -> List[str]:
        """Generate recommendations for lending management."""
        recommendations = []

        if len(overdue) > 0:
            recommendations.append(
                f"Follow up on {len(overdue)} overdue return(s). "
                "Contact borrowing hospitals to arrange returns."
            )

        # Check for imbalanced hospitals
        highly_imbalanced = [h for h in hospital_balances if abs(h["net_balance"]) >= 10]
        if highly_imbalanced:
            recommendations.append(
                f"{len(highly_imbalanced)} hospital(s) have significant lending imbalances. "
                "Consider reviewing reciprocal lending agreements."
            )

        if not recommendations:
            recommendations.append("Lending network is operating smoothly. Continue monitoring.")

        return recommendations
