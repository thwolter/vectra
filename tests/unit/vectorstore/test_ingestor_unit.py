from unittest.mock import AsyncMock, create_autospec

import pytest

from app.repositories import IngestionRepository, JobRepository
from app.schemas.enums import CollectionEnum
from app.vector.ingestor import DocumentIngestor
from app.vector.models import IngestorSettings


@pytest.fixture
def ingestor():
    # Note: DocumentIngestor uses Ingestion classmethods directly; this repo mock is unused
    ing_repo = create_autospec(IngestionRepository, instance=True)
    ing_repo.create = AsyncMock(return_value=None)
    ing_repo.exists = AsyncMock(return_value=False)

    job_repo = create_autospec(JobRepository, instance=True)

    ingestor = DocumentIngestor(CollectionEnum.DEFAULT.value, config=IngestorSettings())
    ingestor._job_repo = job_repo
    ingestor._ingestion_repo = ing_repo
    return ingestor
