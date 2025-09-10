from typing import TYPE_CHECKING, List

from loguru import logger

from .utils import get_doc_content, estimate_text_tokens

if TYPE_CHECKING:
    from .models import IngestorSettings
    from langchain_core.documents import Document


class BatchBuilder:
    """Responsible for grouping documents into batches based on token and count limits."""

    def __init__(self, settings: 'IngestorSettings') -> None:
        self.settings = settings

    def batch_documents_by_tokens(
        self, docs: List['Document']
    ) -> List[List['Document']]:
        """Batch documents by token count and max docs per batch.

        Rules:
        - No batch exceeds max_tokens_per_request in total estimated tokens.
        - No batch contains more than max_docs_per_batch documents.
        - Documents exceeding max_tokens_per_request on their own are skipped with a warning.
        """
        if not docs:
            return []

        batches: List[List['Document']] = []
        current_batch: List['Document'] = []
        current_tokens = 0

        for doc in docs:
            content = get_doc_content(doc)
            tokens = estimate_text_tokens(content)

            if tokens > self.settings.max_tokens_per_request:
                logger.warning(
                    f'Document exceeds max_tokens: {tokens} > {self.settings.max_tokens_per_request}, skipping doc.'
                )
                continue

            over_token_limit = (
                current_tokens + tokens > self.settings.max_tokens_per_request
            )
            over_doc_limit = len(current_batch) >= self.settings.max_docs_per_batch

            if over_token_limit or over_doc_limit:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [doc]
                current_tokens = tokens
            else:
                current_batch.append(doc)
                current_tokens += tokens

        if current_batch:
            batches.append(current_batch)
        return batches
