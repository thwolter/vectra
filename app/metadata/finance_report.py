from typing import List

from langchain_core.documents import Document

from app.metadata.base import Strategy
from app.metadata.schemas import (
    AssessmentResult,
    FinanceReportMetadata,
    ProposedMetadata,
)


def _validate_year(y: int) -> bool:
    return 1900 <= int(y) <= 2100


class FinanceReportStrategy(Strategy):
    metadata_model = FinanceReportMetadata

    def proposed_metadata(self) -> ProposedMetadata:
        hints_dict = self.hints.model_dump(exclude_none=False, exclude={'strategy'})
        conflicts = [key for key, value in hints_dict.items() if value is None]

        return ProposedMetadata(
            metadata=self.hints.model_dump(exclude_none=True, exclude={'strategy'}),
            confidence={},
            conflicts=conflicts,
        )

    def retrieval_query(self) -> str:
        # Construct a simple, semantically rich query from available hints
        tokens: list[str] = [
            'company identity',
            'legal name',
            'reporting year',
            'document type',
        ]
        company = getattr(self.hints, 'company', None)
        if company:
            tokens.append(f'company "{company}"')
        reporting_year = getattr(self.hints, 'reporting_year', None)
        if reporting_year is not None:
            tokens.extend(['financial year', str(reporting_year)])
        doc_type = getattr(self.hints, 'doc_type', None)
        if doc_type:
            mapped = {
                'annual_report': 'annual report',
                '10-K': 'form 10-K',
                '10-Q': 'form 10-Q',
                'interim': 'interim report',
                'press_release': 'press release',
            }.get(doc_type, str(doc_type))
            tokens.extend([mapped])
        seen: set[str] = set()
        deduped = [t for t in tokens if not (t in seen or seen.add(t))]
        return ' '.join(deduped)

    def system_prompt(self) -> str:
        lines: list[str] = [
            'You extract structured metadata from financial/company documents.',
            "Return ONLY the fields required by the schema. Be conservative: prefer 'null' over guessing.",
            'Respond with a JSON object containing keys: metadata (with company, financial_year, document_type), confidence (an object), and conflicts (an array). Do not include any additional keys.',
        ]
        company = getattr(self.hints, 'company', None)
        year = getattr(self.hints, 'reporting_year', None)
        dtype = getattr(self.hints, 'doc_type', None)
        if company:
            lines.append(f'Company hint: {company} (may appear in variants)')
        if year is not None:
            lines.append(f'Year hint: {year}')
        if dtype:
            lines.append(f'Doc type hint: {dtype}')
        return ' '.join(lines)

    def user_prompt(self, context: str) -> str:
        return (
            'From the following context, extract: company (legal name as printed), reporting financial year (YYYY), and document type (e.g., Annual Report, 10-K, 10-Q, Prospectus). If uncertain, use null.\n\n'
            'Context:\n' + context
        )

    def assess_quality(self, *, metadata: ProposedMetadata, docs: List[Document]) -> AssessmentResult:
        """Assess quality using a simple evidence rule.

        Current heuristic: pass if each provided evidence item has score > 0.75
        and a non-empty snippet. Otherwise fail.
        """
        md_all = metadata.metadata or {}
        evidence = {}
        if isinstance(md_all, dict):
            evidence = md_all.get('evidence') or {}

        total_fields = 0
        valid_fields = 0
        if isinstance(evidence, dict):
            for ev in evidence.values():
                total_fields += 1
                if isinstance(ev, dict):
                    ev_score = float(ev.get('score', 0.0) or 0.0)
                    ev_snippet = str(ev.get('snippet') or '').strip()
                    if ev_score > 0.75 and bool(ev_snippet):
                        valid_fields += 1

        all_valid = total_fields > 0 and valid_fields == total_fields
        score = 1.0 if all_valid else 0.0
        details = {
            'total_fields': total_fields,
            'valid_fields': valid_fields,
            'criterion': 'score > 0.75 and non-empty snippet',
        }
        return AssessmentResult(score=score, details=details)
