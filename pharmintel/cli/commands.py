"""
Command-line interface for PharmIntel.
"""
import click
import logging
from pathlib import Path
from datetime import date

from pharmintel.core.database import get_database, init_database
from pharmintel.core.data_loader import import_pharmaceutical_data, seed_sample_hospitals
from pharmintel.analyzers.pharmacogenomics import PharmacogenomicsAnalyzer
from pharmintel.analyzers.gap_analysis import FormularyGapAnalyzer
from pharmintel.analyzers.enhancement import EnhancementAnalyzer
from pharmintel.analyzers.non_formulary import NonFormularyEvaluator
from pharmintel.tracking.expiry_tracker import ExpiryTracker
from pharmintel.tracking.inventory import InventoryManager
from pharmintel.tracking.lending_tracker import LendingTracker
from pharmintel.reports.generator import ReportGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """PharmIntel - Pharmaceutical Intelligence System CLI"""
    pass


# Database commands
@cli.group()
def database():
    """Database management commands."""
    pass


@database.command("init")
@click.option("--reset", is_flag=True, help="Reset database (WARNING: deletes all data)")
def init_db(reset):
    """Initialize database."""
    if reset:
        if click.confirm("Are you sure you want to reset the database? This will delete all data."):
            init_database(reset=True)
            click.echo("✓ Database reset and initialized")
        else:
            click.echo("Operation cancelled")
    else:
        init_database(reset=False)
        click.echo("✓ Database initialized")


@database.command("stats")
def db_stats():
    """Show database statistics."""
    db = get_database()
    stats = db.get_table_info()

    click.echo("\n📊 Database Statistics:")
    click.echo("=" * 50)

    for table_name, count in stats.items():
        click.echo(f"  {table_name:30} {count:>10} rows")


# Data import commands
@cli.group()
def import_data():
    """Data import commands."""
    pass


@import_data.command("excel")
@click.argument("excel_path", type=click.Path(exists=True))
@click.option("--sheet", default=0, help="Sheet name or index")
def import_excel(excel_path, sheet):
    """Import pharmaceutical data from Excel file."""
    click.echo(f"Importing data from: {excel_path}")

    try:
        stats = import_pharmaceutical_data(excel_path, sheet_name=sheet)
        click.echo(f"\n✓ Import complete!")
        click.echo(f"  Successful: {stats['successful']}")
        click.echo(f"  Failed: {stats['failed']}")
    except Exception as e:
        click.echo(f"✗ Import failed: {e}", err=True)


@import_data.command("seed-hospitals")
def seed_hospitals():
    """Seed sample hospital data."""
    db = get_database()

    with db.get_session() as session:
        seed_sample_hospitals(session)
        click.echo("✓ Sample hospitals seeded")


# Analysis commands
@cli.group()
def analyze():
    """Run various analyses."""
    pass


@analyze.command("gap")
@click.option("--format", type=click.Choice(["json", "html"]), default="json")
def gap_analysis(format):
    """Run formulary gap analysis."""
    click.echo("Running gap analysis...")

    db = get_database()
    with db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)
        report = analyzer.generate_comprehensive_report()

        # Generate report file
        generator = ReportGenerator()
        report_path = generator.generate_gap_analysis_report(report, format=format)

        click.echo(f"\n✓ Gap analysis complete!")
        click.echo(f"  Total gaps: {report['summary']['total_gaps_identified']}")
        click.echo(f"  Critical: {report['summary']['critical_gaps']}")
        click.echo(f"  Report saved: {report_path}")


@analyze.command("expiry")
@click.option("--days", default=90, help="Days to look ahead")
def expiry_analysis(days):
    """Run expiry tracking analysis."""
    click.echo(f"Analyzing expiry (next {days} days)...")

    db = get_database()
    with db.get_session() as session:
        tracker = ExpiryTracker(session)
        report = tracker.generate_expiry_report()

        click.echo(f"\n✓ Expiry analysis complete!")
        click.echo(f"  Total alerts: {report['summary']['total_alerts']}")
        click.echo(f"  Critical: {report['summary']['critical_alerts']}")


@analyze.command("inventory")
def inventory_analysis():
    """Run inventory intelligence analysis."""
    click.echo("Analyzing inventory...")

    db = get_database()
    with db.get_session() as session:
        manager = InventoryManager(session)
        report = manager.generate_inventory_report()

        click.echo(f"\n✓ Inventory analysis complete!")
        click.echo(f"  Drugs in stock: {report['summary']['drugs_in_stock']}")
        click.echo(f"  Critical alerts: {report['summary']['critical_alerts']}")
        click.echo(f"  Slow moving items: {report['summary']['slow_moving_items']}")


@analyze.command("lending")
def lending_analysis():
    """Run lending activity analysis."""
    click.echo("Analyzing lending activity...")

    db = get_database()
    with db.get_session() as session:
        tracker = LendingTracker(session)
        report = tracker.generate_lending_report()

        click.echo(f"\n✓ Lending analysis complete!")
        click.echo(f"  Total transactions: {report['summary']['total_transactions']}")
        click.echo(f"  Active lendings: {report['summary']['active_lendings']}")
        click.echo(f"  Overdue returns: {report['summary']['overdue_returns']}")


@analyze.command("non-formulary")
@click.option("--days", default=180, help="Days to look back")
def non_formulary_analysis(days):
    """Run non-formulary drug analysis."""
    click.echo(f"Analyzing non-formulary usage ({days} days)...")

    db = get_database()
    with db.get_session() as session:
        evaluator = NonFormularyEvaluator(session)
        report = evaluator.generate_comprehensive_report(lookback_days=days)

        click.echo(f"\n✓ Non-formulary analysis complete!")
        click.echo(f"  Total non-formulary drugs: {report['summary']['total_non_formulary_drugs']}")
        click.echo(f"  Promotion candidates: {report['summary']['promotion_candidates']}")
        click.echo(f"  Cost impact: ${report['summary']['total_cost_impact']:,.2f}")


@analyze.command("pharmacogenomics")
@click.option("--drug-id", type=int, help="Specific drug ID to analyze")
def pgx_analysis(drug_id):
    """Run pharmacogenomics analysis."""
    db = get_database()

    with db.get_session() as session:
        analyzer = PharmacogenomicsAnalyzer(session)

        if drug_id:
            click.echo(f"Analyzing PGx for drug ID: {drug_id}")
            try:
                report = analyzer.generate_pgx_report(drug_id)
                click.echo(f"\n✓ PGx analysis complete!")
                click.echo(f"  Drug: {report['drug_info']['name']}")
                click.echo(f"  Total interactions: {report['pgx_summary']['total_interactions']}")
                click.echo(f"  High significance: {report['pgx_summary']['high_significance']}")
            except ValueError as e:
                click.echo(f"✗ Error: {e}", err=True)
        else:
            click.echo("Running bulk PGx analysis...")
            results = analyzer.bulk_analyze_formulary()
            click.echo(f"\n✓ PGx analysis complete!")
            click.echo(f"  Total drugs: {results['total_drugs']}")
            click.echo(f"  Drugs with PGx: {results['drugs_with_pgx']}")
            click.echo(f"  High priority drugs: {len(results['high_priority_drugs'])}")


@analyze.command("all")
@click.option("--format", type=click.Choice(["json", "html"]), default="json")
def all_analyses(format):
    """Run all analyses and generate executive summary."""
    click.echo("Running comprehensive analysis...")

    db = get_database()
    generator = ReportGenerator()

    with db.get_session() as session:
        # Run all analyses
        gap_analyzer = FormularyGapAnalyzer(session)
        expiry_tracker = ExpiryTracker(session)
        inventory_manager = InventoryManager(session)
        lending_tracker = LendingTracker(session)
        non_formulary_evaluator = NonFormularyEvaluator(session)

        all_data = {
            "gap_analysis": gap_analyzer.generate_comprehensive_report(),
            "expiry": expiry_tracker.generate_expiry_report(),
            "inventory": inventory_manager.generate_inventory_report(),
            "lending": lending_tracker.generate_lending_report(),
            "non_formulary": non_formulary_evaluator.generate_comprehensive_report()
        }

        # Generate executive summary
        report_path = generator.generate_executive_summary(all_data, format=format)

        click.echo(f"\n✓ Comprehensive analysis complete!")
        click.echo(f"  Executive summary saved: {report_path}")


# Server commands
@cli.group()
def server():
    """Server management commands."""
    pass


@server.command("api")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def run_api(host, port, reload):
    """Start the FastAPI REST API server."""
    import uvicorn

    click.echo(f"Starting API server on {host}:{port}")

    uvicorn.run(
        "pharmintel.api.rest_api:app",
        host=host,
        port=port,
        reload=reload
    )


@server.command("dashboard")
@click.option("--port", default=8501, help="Port to bind to")
def run_dashboard(port):
    """Start the Streamlit dashboard."""
    import subprocess

    click.echo(f"Starting dashboard on port {port}")

    subprocess.run([
        "streamlit",
        "run",
        "pharmintel/web/dashboard.py",
        "--server.port",
        str(port)
    ])


# Report generation commands
@cli.group()
def report():
    """Report generation commands."""
    pass


@report.command("generate")
@click.argument("report_type", type=click.Choice([
    "gap", "expiry", "inventory", "lending", "non-formulary", "executive"
]))
@click.option("--format", type=click.Choice(["json", "html"]), default="json")
def generate_report(report_type, format):
    """Generate specific report."""
    click.echo(f"Generating {report_type} report...")

    db = get_database()
    generator = ReportGenerator()

    with db.get_session() as session:
        if report_type == "gap":
            analyzer = FormularyGapAnalyzer(session)
            data = analyzer.generate_comprehensive_report()
            path = generator.generate_gap_analysis_report(data, format)
        elif report_type == "expiry":
            tracker = ExpiryTracker(session)
            data = tracker.generate_expiry_report()
            path = generator.generate_expiry_report(data, format)
        elif report_type == "inventory":
            manager = InventoryManager(session)
            data = manager.generate_inventory_report()
            path = generator.generate_inventory_report(data, format)
        elif report_type == "lending":
            tracker = LendingTracker(session)
            data = tracker.generate_lending_report()
            path = generator.generate_lending_report(data, format)
        elif report_type == "non-formulary":
            evaluator = NonFormularyEvaluator(session)
            data = evaluator.generate_comprehensive_report()
            path = generator.generate_non_formulary_report(data, format)
        elif report_type == "executive":
            # Gather all data
            all_data = {
                "gap_analysis": FormularyGapAnalyzer(session).generate_comprehensive_report(),
                "expiry": ExpiryTracker(session).generate_expiry_report(),
                "inventory": InventoryManager(session).generate_inventory_report(),
                "lending": LendingTracker(session).generate_lending_report(),
                "non_formulary": NonFormularyEvaluator(session).generate_comprehensive_report()
            }
            path = generator.generate_executive_summary(all_data, format)

        click.echo(f"✓ Report generated: {path}")


def main():
    """Main entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
