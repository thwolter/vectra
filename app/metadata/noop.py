from typing import List

from langchain_core.documents import Document

from app.metadata.base import Strategy
from app.metadata.schemas import AssessmentResult, ProposedMetadata


class NoopStrategy(Strategy):
    def system_prompt(self) -> str:
        return ''

    def user_prompt(self, context: str) -> str:
        return ''

    def assess_quality(self, metadata: ProposedMetadata, docs: List[Document]) -> AssessmentResult:
        return AssessmentResult(score=1.0, details={})

    def retrieval_query(self) -> str:
        return ''

    def proposed_metadata(self) -> ProposedMetadata:
        return ProposedMetadata(
            metadata={},
            confidence={},
            conflicts=[],
        )
