import asyncio
import json
import os

import requests

from core.config import get_settings
from schemas.documents import DocumentContent

settings = get_settings()


class ChatDocParser:
    # API URLs
    api_url: str = 'https://api.chatdoc.com'
    upload_url: str = f'{api_url}/api/v2/documents/upload'
    extract_url: str = f'{api_url}/api/v2/pdf_parser'

    # Document status constants
    UN_PARSED = 1  # file uploaded or collection has no document
    ELEMENT_PARSED = 300  # analysis of the document has succeeded
    # ERROR_STATUSES are any status < 0

    def __init__(self):
        if not settings.chatdoc_api_key:
            raise Exception('ChatDoc API key not set')

        self.api_key = settings.chatdoc_api_key.get_secret_value()

        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    def get_extract_url(self, upload_id: str) -> str:
        """
        Returns the URL for extracting text from an uploaded file.

        Args:
            upload_id: The ID of the uploaded document.

        Returns:
            The extraction URL.
        """
        return f'{self.api_url}/api/v2/pdf_parser/{upload_id}'

    def get_document_url(self, upload_id: str) -> str:
        """
        Returns the URL for checking the status of an uploaded document.

        Args:
            upload_id: The ID of the uploaded document.

        Returns:
            The document URL.
        """
        return f'{self.api_url}/api/v2/documents/{upload_id}'

    async def check_document_status(self, upload_id: str) -> int:
        """
        Checks the status of an uploaded document.

        Args:
            upload_id: The ID of the uploaded document.

        Returns:
            The status code of the document.
        """
        response = requests.get(self.get_document_url(upload_id), headers=self.headers)
        response.raise_for_status()

        data = response.json().get('data', {})
        return data.get('status', self.UN_PARSED)

    async def parse(self, file_path: str) -> DocumentContent:
        """
        Parses a document file and returns its content.

        This method uploads the file, polls for document status until it's finalized,
        and then extracts the document content. The polling interval is 10 seconds,
        and the process typically takes 1-2 minutes depending on the document size.

        Args:
            file_path: The path to the document file.

        Returns:
            The parsed document content.

        Raises:
            Exception: If an error occurs during document analysis or if the process times out.
        """
        upload_id = await self.upload_file(file_path)

        # Poll the document status until it's finalized
        max_attempts = 36  # 6 minutes (36 * 10 seconds)
        attempts = 0

        while attempts < max_attempts:
            status = await self.check_document_status(upload_id)

            # Check if the status is finalized
            if status == self.ELEMENT_PARSED:
                # Document is successfully parsed, proceed to extraction
                break
            elif status < 0:
                # Error occurred during analysis
                raise Exception(f'Error occurred during document analysis. Status code: {status}')

            # Status is still UN_PARSED or in progress, wait and try again
            await asyncio.sleep(10)  # Wait for 10 seconds before polling again
            attempts += 1

        if attempts >= max_attempts:
            raise Exception('Timeout waiting for document to be processed')

        # Document is ready for extraction
        extract_response = requests.get(self.get_extract_url(upload_id), headers=self.headers)
        extract_response.raise_for_status()

        data = json.loads(extract_response.text)['data']
        return DocumentContent(content=data.get('elements', []), metadata=data.get('document', {}))

    async def upload_file(self, file_path: str) -> str:
        with open(file_path, 'rb') as file:
            files = {'file': (os.path.basename(file_path), file, 'application/pdf')}
            data = {'package_type': 'basic'}
            headers = {'Authorization': f'Bearer {self.api_key}'}
            response = requests.post(self.upload_url, headers=headers, files=files, data=data)
            response.raise_for_status()
            return response.json()['data']['id']


parser = ChatDocParser()
