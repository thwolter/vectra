import pickle
from pathlib import Path
from typing import List

import pytest
from langchain_core.documents import Document


@pytest.fixture
def sample_documents() -> List[Document]:
    """Load sample documents from pickle file for vectorstore tests only.

    Keeps the root tests/conftest.py lean while preserving this fixture where it's needed.
    """
    sample_path = Path(__file__).parents[2] / 'data' / 'sample_docs.pkl'
    with open(sample_path, 'rb') as f:
        return pickle.load(f)
