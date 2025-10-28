"""
Unit tests for gap analysis module.
"""
import pytest
from pharmintel.core.database import Database
from pharmintel.core.models import Drug, TherapeuticArea, FormularyStatus
from pharmintel.analyzers.gap_analysis import FormularyGapAnalyzer


@pytest.fixture
def test_db():
    """Create test database."""
    db = Database(database_url="sqlite:///:memory:")
    db.create_all_tables()
    return db


@pytest.fixture
def sample_drugs(test_db):
    """Create sample drugs for testing."""
    with test_db.get_session() as session:
        drugs = [
            Drug(
                material="Atenolol 50mg Tablet",
                material_number="100001",
                therapeutic_area=TherapeuticArea.CARDIOLOGY,
                formulary_status=FormularyStatus.FORMULARY
            ),
            Drug(
                material="Amoxicillin 500mg Capsule",
                material_number="100002",
                therapeutic_area=TherapeuticArea.INFECTIOUS_DISEASE,
                formulary_status=FormularyStatus.FORMULARY
            ),
            Drug(
                material="Metformin 500mg Tablet",
                material_number="100003",
                therapeutic_area=TherapeuticArea.INTERNAL_MEDICINE,
                formulary_status=FormularyStatus.FORMULARY
            )
        ]

        for drug in drugs:
            session.add(drug)

        session.commit()

    return drugs


def test_gap_analyzer_initialization(test_db):
    """Test gap analyzer initialization."""
    with test_db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)
        assert analyzer is not None
        assert analyzer.session == session


def test_therapeutic_area_coverage(test_db, sample_drugs):
    """Test therapeutic area coverage analysis."""
    with test_db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)

        # Test Cardiology coverage
        coverage = analyzer.analyze_therapeutic_area_coverage("Cardiology")

        assert "therapeutic_area" in coverage
        assert coverage["therapeutic_area"] == "Cardiology"
        assert "formulary_drug_count" in coverage
        assert coverage["formulary_drug_count"] >= 1
        assert "coverage_percentage" in coverage


def test_identify_gaps(test_db, sample_drugs):
    """Test gap identification."""
    with test_db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)

        gaps = analyzer.identify_gaps()

        assert isinstance(gaps, list)
        # Should have some gaps since we only have 3 drugs
        assert len(gaps) > 0

        # Check gap structure
        if gaps:
            gap = gaps[0]
            assert hasattr(gap, "gap_type")
            assert hasattr(gap, "therapeutic_area")
            assert hasattr(gap, "severity")
            assert hasattr(gap, "recommendation")


def test_coverage_heatmap_data(test_db, sample_drugs):
    """Test coverage heatmap data generation."""
    with test_db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)

        heatmap_data = analyzer.generate_coverage_heatmap_data()

        assert "areas" in heatmap_data
        assert "coverage" in heatmap_data
        assert "drug_counts" in heatmap_data
        assert "missing_counts" in heatmap_data

        assert len(heatmap_data["areas"]) == len(heatmap_data["coverage"])


def test_comprehensive_report(test_db, sample_drugs):
    """Test comprehensive report generation."""
    with test_db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)

        report = analyzer.generate_comprehensive_report()

        assert "summary" in report
        assert "gaps_by_severity" in report
        assert "coverage_heatmap" in report
        assert "recommendations" in report

        # Check summary structure
        summary = report["summary"]
        assert "total_drugs" in summary
        assert "total_gaps_identified" in summary


def test_empty_database(test_db):
    """Test analyzer with empty database."""
    with test_db.get_session() as session:
        analyzer = FormularyGapAnalyzer(session)

        coverage = analyzer.analyze_therapeutic_area_coverage("Cardiology")

        assert coverage["formulary_drug_count"] == 0
        assert coverage["coverage_percentage"] < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
