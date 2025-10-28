"""
Streamlit web dashboard for PharmIntel.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

from pharmintel.core.database import get_database
from pharmintel.analyzers.gap_analysis import FormularyGapAnalyzer
from pharmintel.analyzers.pharmacogenomics import PharmacogenomicsAnalyzer
from pharmintel.analyzers.enhancement import EnhancementAnalyzer
from pharmintel.analyzers.non_formulary import NonFormularyEvaluator
from pharmintel.tracking.expiry_tracker import ExpiryTracker
from pharmintel.tracking.inventory import InventoryManager
from pharmintel.tracking.lending_tracker import LendingTracker
from pharmintel.core.models import Drug

# Page configuration
st.set_page_config(
    page_title="PharmIntel Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .critical { color: #d62728; font-weight: bold; }
    .warning { color: #ff7f0e; font-weight: bold; }
    .success { color: #2ca02c; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db():
    """Get database instance."""
    return get_database()


def main():
    """Main dashboard function."""

    # Header
    st.markdown('<div class="main-header">💊 PharmIntel Dashboard</div>', unsafe_allow_html=True)
    st.markdown("**Pharmaceutical Intelligence System**")
    st.markdown("---")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Module",
        [
            "🏠 Overview",
            "📊 Gap Analysis",
            "🧬 Pharmacogenomics",
            "📅 Expiry Tracking",
            "📦 Inventory Management",
            "🔄 Inter-Hospital Lending",
            "💊 Non-Formulary Analysis",
            "💡 Enhancement Recommendations"
        ]
    )

    # Page routing
    if page == "🏠 Overview":
        show_overview()
    elif page == "📊 Gap Analysis":
        show_gap_analysis()
    elif page == "🧬 Pharmacogenomics":
        show_pharmacogenomics()
    elif page == "📅 Expiry Tracking":
        show_expiry_tracking()
    elif page == "📦 Inventory Management":
        show_inventory_management()
    elif page == "🔄 Inter-Hospital Lending":
        show_lending_tracker()
    elif page == "💊 Non-Formulary Analysis":
        show_non_formulary()
    elif page == "💡 Enhancement Recommendations":
        show_enhancement_recommendations()


def show_overview():
    """Show overview dashboard."""
    st.header("📊 System Overview")

    db = get_db()

    with db.get_session() as session:
        # Get summary statistics
        total_drugs = session.query(Drug).count()
        formulary_drugs = session.query(Drug).filter(Drug.formulary_status == "FORMULARY").count()

        # Create metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Drugs", total_drugs)

        with col2:
            st.metric("Formulary Drugs", formulary_drugs)

        with col3:
            st.metric("Non-Formulary", total_drugs - formulary_drugs)

        with col4:
            coverage = (formulary_drugs / total_drugs * 100) if total_drugs > 0 else 0
            st.metric("Formulary Coverage", f"{coverage:.1f}%")

        st.markdown("---")

        # Quick insights
        st.subheader("Quick Insights")

        col1, col2 = st.columns(2)

        with col1:
            # Expiry alerts
            tracker = ExpiryTracker(session)
            critical_alerts = tracker.get_critical_alerts()
            st.warning(f"⚠️ **{len(critical_alerts)} Critical Expiry Alerts**")

            # Inventory alerts
            manager = InventoryManager(session)
            stock_alerts = manager.check_stock_levels()
            critical_stock = [a for a in stock_alerts if a.alert_level == "critical"]
            st.error(f"🚨 **{len(critical_stock)} Critical Stock Alerts**")

        with col2:
            # Gap analysis summary
            gap_analyzer = FormularyGapAnalyzer(session)
            gaps = gap_analyzer.identify_gaps()
            critical_gaps = [g for g in gaps if g.severity == "critical"]
            st.info(f"📊 **{len(critical_gaps)} Critical Formulary Gaps**")

            # Lending activity
            lending_tracker = LendingTracker(session)
            pending_requests = lending_tracker.get_pending_requests()
            st.info(f"🔄 **{len(pending_requests)} Pending Lending Requests**")


def show_gap_analysis():
    """Show gap analysis page."""
    st.header("📊 Formulary Gap Analysis")

    db = get_db()

    with db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)

        # Get comprehensive report
        report = analyzer.generate_comprehensive_report()

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Gaps", report["summary"]["total_gaps_identified"])

        with col2:
            st.metric("Critical Gaps", report["summary"]["critical_gaps"], delta_color="inverse")

        with col3:
            st.metric("High Priority", report["summary"]["high_priority_gaps"])

        with col4:
            st.metric("WHO Coverage", f"{report['summary']['average_who_coverage']:.1f}%")

        st.markdown("---")

        # Coverage heatmap
        st.subheader("Coverage by Therapeutic Area")

        heatmap_data = report["coverage_heatmap"]

        fig = go.Figure(data=go.Bar(
            x=heatmap_data["areas"],
            y=heatmap_data["coverage"],
            marker=dict(
                color=heatmap_data["coverage"],
                colorscale="RdYlGn",
                showscale=True
            ),
            text=[f"{c:.1f}%" for c in heatmap_data["coverage"]],
            textposition="auto"
        ))

        fig.update_layout(
            title="WHO Essential Medicines Coverage",
            xaxis_title="Therapeutic Area",
            yaxis_title="Coverage (%)",
            height=400
        )

        st.plotly_chart(fig, use_container_width=True)

        # Gaps table
        st.subheader("Identified Gaps")

        gaps_df = pd.DataFrame([
            {
                "Therapeutic Area": g.therapeutic_area,
                "Gap Type": g.gap_type,
                "Severity": g.severity,
                "Description": g.description,
                "Priority Score": g.priority_score
            }
            for g in report["gaps_by_severity"]["critical"] + report["gaps_by_severity"]["high"]
        ])

        if not gaps_df.empty:
            st.dataframe(gaps_df, use_container_width=True)
        else:
            st.success("✅ No critical or high-priority gaps identified!")


def show_pharmacogenomics():
    """Show pharmacogenomics analysis page."""
    st.header("🧬 Pharmacogenomics Analysis")

    db = get_db()

    with db.get_session() as session:
        analyzer = PharmacogenomicsAnalyzer(session)

        # Bulk analysis
        results = analyzer.bulk_analyze_formulary()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Drugs", results["total_drugs"])

        with col2:
            st.metric("Drugs with PGx", results["drugs_with_pgx"])

        with col3:
            st.metric("High Priority", len(results["high_priority_drugs"]))

        st.markdown("---")

        # High priority drugs
        if results["high_priority_drugs"]:
            st.subheader("High-Priority Pharmacogenomic Interactions")

            pgx_df = pd.DataFrame(results["high_priority_drugs"])
            st.dataframe(pgx_df, use_container_width=True)

        # By therapeutic area
        st.subheader("PGx Distribution by Therapeutic Area")

        if results["by_therapeutic_area"]:
            area_data = pd.DataFrame([
                {"Therapeutic Area": k, "Drug Count": v}
                for k, v in results["by_therapeutic_area"].items()
            ])

            fig = px.pie(
                area_data,
                values="Drug Count",
                names="Therapeutic Area",
                title="Drugs with PGx Considerations"
            )

            st.plotly_chart(fig, use_container_width=True)


def show_expiry_tracking():
    """Show expiry tracking page."""
    st.header("📅 Expiry Tracking & Management")

    db = get_db()

    with db.get_session() as session:
        tracker = ExpiryTracker(session)

        # Get alerts
        all_alerts = tracker.get_all_expiring_batches()
        critical_alerts = [a for a in all_alerts if a.alert_level == "critical"]
        warning_alerts = [a for a in all_alerts if a.alert_level == "warning"]

        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Alerts", len(all_alerts))

        with col2:
            st.metric("Critical (< 30 days)", len(critical_alerts), delta_color="inverse")

        with col3:
            st.metric("Warning (30-60 days)", len(warning_alerts), delta_color="inverse")

        with col4:
            info_alerts = [a for a in all_alerts if a.alert_level == "info"]
            st.metric("Info (60-90 days)", len(info_alerts))

        st.markdown("---")

        # Critical alerts table
        if critical_alerts:
            st.subheader("🚨 Critical Expiry Alerts")

            critical_df = pd.DataFrame([
                {
                    "Drug": a.drug_name,
                    "Batch": a.batch_number,
                    "Expiry Date": a.expiry_date,
                    "Days Left": a.days_until_expiry,
                    "Quantity": a.quantity,
                    "Wastage Risk": a.estimated_wastage_risk,
                    "Recommendation": a.recommendation
                }
                for a in critical_alerts[:20]
            ])

            st.dataframe(
                critical_df.style.apply(
                    lambda x: ["background-color: #ffcccb" if x.name in critical_df.index else "" for _ in x],
                    axis=1
                ),
                use_container_width=True
            )

        # Distribution chart
        st.subheader("Expiry Distribution")

        alert_counts = {
            "Critical": len(critical_alerts),
            "Warning": len(warning_alerts),
            "Info": len(info_alerts)
        }

        fig = go.Figure(data=[go.Bar(
            x=list(alert_counts.keys()),
            y=list(alert_counts.values()),
            marker=dict(color=["#d62728", "#ff7f0e", "#1f77b4"])
        )])

        fig.update_layout(title="Alerts by Severity", height=300)
        st.plotly_chart(fig, use_container_width=True)


def show_inventory_management():
    """Show inventory management page."""
    st.header("📦 Inventory Management")

    db = get_db()

    with db.get_session() as session:
        manager = InventoryManager(session)

        # Get report
        report = manager.generate_inventory_report()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Drugs", report["summary"]["total_drugs"])

        with col2:
            st.metric("In Stock", report["summary"]["drugs_in_stock"])

        with col3:
            st.metric("Stock Out", report["summary"]["stock_out_count"])

        with col4:
            st.metric(
                "Inventory Value",
                f"${report['summary']['total_inventory_value']:,.2f}"
            )

        st.markdown("---")

        # Stock alerts
        if report["stock_alerts"]:
            st.subheader("🚨 Stock Level Alerts")

            alerts_df = pd.DataFrame(report["stock_alerts"])
            st.dataframe(alerts_df, use_container_width=True)

        # Slow moving items
        if report["slow_moving_items"]:
            st.subheader("🐌 Slow-Moving Items")

            slow_df = pd.DataFrame(report["slow_moving_items"])
            st.dataframe(slow_df, use_container_width=True)


def show_lending_tracker():
    """Show lending tracker page."""
    st.header("🔄 Inter-Hospital Lending Tracker")

    db = get_db()

    with db.get_session() as session:
        tracker = LendingTracker(session)

        # Get report
        report = tracker.generate_lending_report()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Transactions", report["summary"]["total_transactions"])

        with col2:
            st.metric("Active Lendings", report["summary"]["active_lendings"])

        with col3:
            st.metric("Completed", report["summary"]["completed_lendings"])

        with col4:
            st.metric("Overdue Returns", report["summary"]["overdue_returns"], delta_color="inverse")

        st.markdown("---")

        # Hospital balances
        if report["hospital_balances"]:
            st.subheader("Hospital Lending Balances")

            balance_df = pd.DataFrame(report["hospital_balances"])
            st.dataframe(balance_df, use_container_width=True)

            # Visualization
            fig = go.Figure(data=[
                go.Bar(
                    name="Lent",
                    x=[b["hospital_name"] for b in report["hospital_balances"]],
                    y=[b["total_lent"] for b in report["hospital_balances"]]
                ),
                go.Bar(
                    name="Borrowed",
                    x=[b["hospital_name"] for b in report["hospital_balances"]],
                    y=[b["total_borrowed"] for b in report["hospital_balances"]]
                )
            ])

            fig.update_layout(barmode="group", title="Hospital Activity", height=400)
            st.plotly_chart(fig, use_container_width=True)


def show_non_formulary():
    """Show non-formulary analysis page."""
    st.header("💊 Non-Formulary Drug Analysis")

    db = get_db()

    with db.get_session() as session:
        evaluator = NonFormularyEvaluator(session)

        # Get report
        report = evaluator.generate_comprehensive_report()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Non-Formulary Drugs", report["summary"]["total_non_formulary_drugs"])

        with col2:
            st.metric("Promotion Candidates", report["summary"]["promotion_candidates"])

        with col3:
            st.metric(
                "Total Cost Impact",
                f"${report['summary']['total_cost_impact']:,.2f}"
            )

        with col4:
            st.metric("Exception Requests", report["summary"]["exception_requests"])

        st.markdown("---")

        # Promotion candidates
        if report["promotion_candidates"]:
            st.subheader("🎯 Formulary Promotion Candidates")

            candidates_df = pd.DataFrame(report["promotion_candidates"])
            st.dataframe(candidates_df, use_container_width=True)


def show_enhancement_recommendations():
    """Show enhancement recommendations page."""
    st.header("💡 Formulary Enhancement Recommendations")

    db = get_db()

    with db.get_session() as session:
        analyzer = EnhancementAnalyzer(session)

        # Get summary
        summary = analyzer.generate_summary_report()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Recommendations", summary["summary"]["total_recommendations"])

        with col2:
            st.metric("High Priority", summary["summary"]["high_priority"])

        with col3:
            st.metric("Medium Priority", summary["summary"]["medium_priority"])

        with col4:
            potential = summary["savings_potential"]["total_potential_savings"]
            st.metric("Potential Savings", f"${potential:,.2f}")

        st.markdown("---")

        # Recommendations by type
        st.subheader("Recommendations by Type")

        type_data = pd.DataFrame([
            {"Type": k, "Count": v}
            for k, v in summary["by_type"].items()
        ])

        fig = px.bar(type_data, x="Type", y="Count", title="Recommendations Distribution")
        st.plotly_chart(fig, use_container_width=True)

        # Top opportunities
        if summary["top_opportunities"]:
            st.subheader("🌟 Top Opportunities")

            top_df = pd.DataFrame([
                {
                    "Type": r.recommendation_type,
                    "Current Drug": r.current_drug or "N/A",
                    "Suggested": r.suggested_drug,
                    "Rationale": r.rationale,
                    "Priority": r.priority,
                    "Savings": f"${r.estimated_savings:,.2f}" if r.estimated_savings else "N/A"
                }
                for r in summary["top_opportunities"][:10]
            ])

            st.dataframe(top_df, use_container_width=True)


if __name__ == "__main__":
    main()
