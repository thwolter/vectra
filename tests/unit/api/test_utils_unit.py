from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from app.api.utils import parse_hints_from_any
from app.metadata.schemas import FinanceReportHints, NoopHints


def test_parse_hints_empty_string_returns_noop():
    hints = parse_hints_from_any('')
    assert isinstance(hints, NoopHints)


def test_parse_hints_json_string_finance():
    raw = {
        'strategy': 'finance_report',
        'company': 'Globex',
        'document_type': '10-Q',
        'financial_year': 2023,
    }
    hints = parse_hints_from_any(json.dumps(raw))
    assert isinstance(hints, FinanceReportHints)
    assert hints.company == 'Globex'
    assert hints.document_type == '10-Q'
    assert hints.financial_year == 2023


def test_parse_hints_unknown_strategy_raises_422():
    raw = {'strategy': 'unknown'}
    with pytest.raises(HTTPException) as exc:
        parse_hints_from_any(json.dumps(raw))
    err = exc.value
    assert err.status_code == 422
    assert 'Invalid hints' in str(err.detail)


def test_parse_hints_malformed_json_raises_422():
    bad_json = '{this is not: valid json]'
    with pytest.raises(HTTPException) as exc:
        parse_hints_from_any(bad_json)
    err = exc.value
    assert err.status_code == 422
    assert 'Invalid hints' in str(err.detail)
