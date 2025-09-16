from unittest.mock import create_autospec

import pytest

from app.metadata.base import Strategy
from app.metadata.finance_report import FinanceReportStrategy
from app.metadata.noop import NoopStrategy
from app.metadata.schemas import FinanceReportHints, NoopHints, ProposedMetadata


def test_metadata_strategy_returns_finance_report_class():
    hints = FinanceReportHints(
        company='Acme Inc',
        document_type='10-K',
        financial_year=2024,
    )

    strategy = Strategy.from_hints(hints=hints)
    assert isinstance(strategy, FinanceReportStrategy)


def test_metadata_strategy_returns_noop_class():
    hints = NoopHints()

    strategy = Strategy.from_hints(hints=hints)
    assert isinstance(strategy, NoopStrategy)


def test_metadata_strategy_returns_proposed_metadata():
    hints = FinanceReportHints(
        company='Acme Inc',
        document_type='10-K',
        financial_year=2024,
    )

    strategy = FinanceReportStrategy(hints=hints)
    proposed = strategy.proposed_metadata()

    assert type(proposed) is ProposedMetadata


def test_finance_report_conflicts_include_none_attributes():
    # Given two None fields and one provided field
    hints = FinanceReportHints(
        company=None,
        document_type=None,
        financial_year=2024,
    )

    strategy = FinanceReportStrategy(hints=hints)
    proposed = strategy.proposed_metadata()

    # Conflicts should include exactly the fields that are None
    assert set(proposed.conflicts) == {'company', 'document_type'}
    # Metadata should only include non-None fields
    assert proposed.metadata == {'financial_year': 2024}


def test_prepare_metadata_model_builds_without_error_and_has_expected_fields():
    # Ensure prepare_metadata_model completes and the schema includes expected fields
    hints = FinanceReportHints(company='Acme Inc', document_type='10-K', financial_year=2024)
    strategy = FinanceReportStrategy(hints=hints)

    # Should not raise
    strategy.prepare_metadata_model()

    # FinanceReportMetadata should expose these fields
    assert FinanceReportStrategy.metadata_model is not None
    assert set(FinanceReportStrategy.metadata_model.model_fields.keys()) == {
        'company',
        'financial_year',
        'document_type',
    }


def test_prepare_metadata_model_raises_when_metadata_model_missing():
    # Use autospec to create a Strategy-like instance and bind the real method
    bad_instance = create_autospec(Strategy, instance=True)
    bad_instance.metadata_model = None
    bad_instance.prepare_metadata_model = Strategy.prepare_metadata_model

    # Bind the real implementation so validation logic executes
    from types import MethodType

    bad_instance.prepare_metadata_model = MethodType(Strategy.prepare_metadata_model, bad_instance)

    with pytest.raises(ValueError):
        bad_instance.prepare_metadata_model()
