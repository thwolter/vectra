import importlib
import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Type, Any, ClassVar

from langchain_core.documents import Document

from app.metadata.schemas import ProposedMetadata, AssessmentResult, Evidence, NoopHints
from app.schemas.upload import UploadHints
from pydantic import create_model, Field, BaseModel


class Strategy(ABC):
    """Base Strategy for metadata extraction and guidance.

    Concrete strategies encapsulate domain-specific retrieval queries and
    prompt templates while staying agnostic to the extractor implementation
    (LangGraph vs Strands-style). Hints are Pydantic models discriminated by
    `strategy` and must not leak into callers beyond this boundary.
    """

    metadata_model: ClassVar[type[BaseModel] | None] = None

    def __init__(self, hints: UploadHints):
        self.hints = hints

    @classmethod
    def from_hints(cls, hints: UploadHints | None = None) -> 'Strategy':
        hints = hints or NoopHints()
        cls_name = Strategy.get_class_name(hints)

        mod = importlib.import_module(f'app.metadata.{hints.strategy}')
        klass = getattr(mod, cls_name, None)
        if klass is None:
            raise AttributeError(
                f"Strategy class {cls_name} not found for name '{hints.strategy}'"
            )
        return klass(hints=hints)

    @classmethod
    def get_class_name(cls, hints):
        return hints.strategy.replace('_', ' ').title().replace(' ', '') + 'Strategy'

    @abstractmethod
    def proposed_metadata(self) -> ProposedMetadata:
        """Return proposed metadata, confidences, and conflicts based on hints."""
        raise NotImplementedError

    @abstractmethod
    def retrieval_query(self) -> str:
        """Return a vector search query tailored to the strategy and hints."""
        raise NotImplementedError

    @abstractmethod
    def system_prompt(self) -> str:
        """LLM system prompt guiding extraction of doc info for this strategy."""
        raise NotImplementedError

    @abstractmethod
    def user_prompt(self, context: str) -> str:
        """LLM user prompt incorporating provided context."""
        raise NotImplementedError

    @staticmethod
    def make_context(docs: List[Document]) -> str:
        # simple concatenation with cap; you can swap in a rank/merge strategy
        max_chars = 6000
        out, left = [], max_chars
        for d in docs:
            chunk = d.page_content[: min(len(d.page_content), left)]
            out.append(chunk)
            left -= len(chunk)
            if left <= 0:
                break
        return '\n\n---\n\n'.join(out)

    @abstractmethod
    def assess_quality(
        self, *, metadata: ProposedMetadata, docs: List[Document]
    ) -> AssessmentResult:
        raise NotImplementedError

    def build_llm_response_model(self) -> Type[BaseModel]:
        """
        Build a pydantic model for structured LLM output:
        - metadata: subset of self.metadata_model, excluding fields provided in hints
        - evidence: Evidence fields matching the same subset
        Returns a model class named 'LLMResponse' with strict validation.
        """

        mm = self.prepare_metadata_model()
        fields_to_include = self.required_fields(mm)

        subset_fields: Dict[str, Any] = {}
        for name in fields_to_include:
            f = mm.model_fields[name]
            subset_fields[name] = (
                f.annotation,
                Field(None, description=getattr(f, 'description', None)),
            )

        MetadataSubset = create_model(
            f'{mm.__name__}Subset',
            **subset_fields,
        )

        # Build a matching evidence model with Evidence-typed fields
        evidence_fields: Dict[str, Any] = {}
        for name in fields_to_include:
            # Describe evidence field in the required form
            human_name = name.replace('_', ' ')
            ev_desc = f'Evidence for the identified {human_name}'
            evidence_fields[name] = (Evidence, Field(..., description=ev_desc))
        EvidenceSubset = create_model(
            f'{mm.__name__}EvidenceSubset',
            **evidence_fields,
        )

        # Return the response schema expected by the extractor: metadata + evidence
        return create_model(
            'LLMResponse',
            metadata=(MetadataSubset, ...),
            evidence=(EvidenceSubset, ...),
        )

    def required_fields(self, mm):
        all_fields = list(mm.model_fields.keys())
        provided = set(self.hints.model_dump(exclude_none=True).keys())
        return [f for f in all_fields if f not in provided]

    def prepare_metadata_model(self) -> type[BaseModel]:
        """Ensure metadata_model is a valid Pydantic model and rebuild it"""
        mm = self.metadata_model
        if mm is None:
            raise ValueError(f'{type(self).__name__}.metadata_model must be set')
        if not issubclass(mm, BaseModel):
            raise ValueError(
                f'{type(self).__name__}.metadata_model must be a Pydantic BaseModel subclass'
            )
        types_ns = vars(sys.modules.get(mm.__module__, sys.modules[__name__]))
        try:
            mm.model_rebuild(_types_namespace=types_ns, force=True)
            return mm
        except NameError:
            mm.model_rebuild(force=True)
            return mm
        except Exception as e:
            raise RuntimeError(f'Failed to rebuild metadata_model: {e}') from e
