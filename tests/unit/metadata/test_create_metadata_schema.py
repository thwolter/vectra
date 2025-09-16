from app.metadata.finance_report import FinanceReportStrategy
from app.metadata.schemas import Evidence, FinanceReportHints


def test_create_metadata_schema_finance_report_filters_hinted_fields():
    # company is provided (hinted), others are missing
    hints = FinanceReportHints(company='Acme Inc', financial_year=None, document_type=None)

    strategy = FinanceReportStrategy(hints=hints)
    SchemaModel = strategy.build_llm_response_model()

    # Schema should contain 'metadata' and 'evidence' fields
    assert 'metadata' in SchemaModel.model_fields
    assert 'evidence' in SchemaModel.model_fields

    # The nested metadata model should only include fields not provided by hints
    metadata_type = SchemaModel.model_fields['metadata'].annotation
    # Access model_fields of the nested pydantic model
    assert hasattr(metadata_type, 'model_fields')
    meta_fields = set(metadata_type.model_fields.keys())

    # company is hinted and should be excluded; remaining expected
    assert meta_fields == {'financial_year', 'document_type'}


def test_create_metadata_schema_evidence_model_fields_and_types():
    hints = FinanceReportHints(company=None, financial_year=None, document_type=None)
    strategy = FinanceReportStrategy(hints=hints)
    SchemaModel = strategy.build_llm_response_model()

    # Evidence must be a model mirroring metadata fields, each of type Evidence
    evidence_type = SchemaModel.model_fields['evidence'].annotation
    assert hasattr(evidence_type, 'model_fields')

    metadata_type = SchemaModel.model_fields['metadata'].annotation
    meta_fields = set(metadata_type.model_fields.keys())
    ev_fields = set(evidence_type.model_fields.keys())
    assert ev_fields == meta_fields

    # Ensure each evidence field is annotated as Evidence
    for name, f in evidence_type.model_fields.items():
        assert f.annotation is Evidence

    # Also validate that an instance can be created with matching keys
    sample_meta = {f: None for f in meta_fields}
    sample_ev = {f: Evidence(score=0.9, snippet='ref') for f in meta_fields}

    obj = SchemaModel(metadata=sample_meta, evidence=sample_ev)
    assert (
        obj.metadata.model_dump() == sample_meta  # pyrefly: ignore[missing-attribute]
    )
    assert obj.evidence.model_dump() == {  # pyrefly: ignore[missing-attribute]
        k: v.model_dump() for k, v in sample_ev.items()
    }


def test_create_metadata_schema_descriptions_propagated_and_evidence_prefixed():
    # Provide a hint for company only, so metadata subset contains financial_year, document_type
    hints = FinanceReportHints(company='Acme Inc', financial_year=None, document_type=None)
    strategy = FinanceReportStrategy(hints=hints)
    SchemaModel = strategy.build_llm_response_model()

    metadata_type = SchemaModel.model_fields['metadata'].annotation
    evidence_type = SchemaModel.model_fields['evidence'].annotation

    # Check metadata field descriptions originate from schema
    fy_field = metadata_type.model_fields['financial_year']
    dt_field = metadata_type.model_fields['document_type']
    assert fy_field.description == 'Reporting financial year (YYYY)'
    assert dt_field.description == 'Document type (e.g., Annual Report, 10-K)'

    # Evidence description should be adjusted to "Evidence for the identified <field>"
    fy_ev = evidence_type.model_fields['financial_year']
    dt_ev = evidence_type.model_fields['document_type']
    assert fy_ev.description == 'Evidence for the identified financial year'
    assert dt_ev.description == 'Evidence for the identified document type'
