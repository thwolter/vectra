from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model for API endpoints."""

    success: bool = Field(..., description='Whether the operation was successful')
    message: str = Field(..., description='Message describing the result of the operation')


class ErrorResponse(BaseResponse):
    """Error response model for API endpoints."""

    success: bool = Field(False, description='Operation was not successful')
    error_code: Optional[str] = Field(None, description='Error code')
    details: Optional[Dict[str, Any]] = Field(None, description='Additional error details')


class UploadResponse(BaseResponse):
    """Response model for file upload endpoint."""

    success: bool = Field(True, description='Operation was successful')
