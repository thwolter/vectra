from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, conint


class AssessmentResult(BaseModel):
    score: float = Field(..., description='Assessment score')
    details: Dict[str, Any] = Field(..., description='Assessment details')


class Evidence(BaseModel):
    score: float = Field(..., description='Confidence score for the evidence')
    snippet: str = Field(..., description='Short text supporting the extracted value')


class ProposedMetadata(BaseModel):
    """System-proposed metadata + confidence and conflicts."""

    metadata: dict = Field(default_factory=dict, description='Proposed metadata')
    confidence: Dict[str, Evidence] = Field(default_factory=dict, description='Confidence scores')
    conflicts: List[str] = Field(default_factory=list, description='Conflicting metadata fields')


class NoopHints(BaseModel):
    """Fallback hints with no specific fields; keeps pipeline moving."""

    strategy: Literal['noop'] = 'noop'


class FinanceReportMetadata(BaseModel):
    """Explicit schema for metadata extracted from financial reports.

    Having an explicit model ensures JSON Schema has additionalProperties=false,
    satisfying OpenAI structured output requirements.
    """

    company: str | None = Field(default=None, description='Legal company name as printed')
    financial_year: conint(ge=1900, le=2100) | None = Field(default=None, description='Reporting financial year (YYYY)')
    document_type: str | None = Field(default=None, description='Document type (e.g., Annual Report, 10-K)')


class FinanceReportHints(FinanceReportMetadata):
    """Hints for parsing financial reports."""

    strategy: Literal['finance_report'] = 'finance_report'
