from pydantic import BaseModel


class ExtractConfig(BaseModel):
    model_name: str = 'gpt-5-mini'
    temperature: float = 0.0
    doc_info_k: int = 6
    max_attempts: int = 3
