import os
from dataclasses import dataclass
from typing import Generator, Any

import pytest
from pydantic import SecretStr
from testcontainers.localstack import LocalStackContainer

from core.config import get_settings

LOCALSTACK_IMAGE = 'localstack/localstack:2.2.0'
LOCALSTACK_S3_BUCKET = 'vectra-documents-localstack'
LOCALSTACK_ACCESS_KEY = 'testcontainers-localstack'
LOCALSTACK_SECRET_KEY = 'testcontainers-localstack'
LOCALSTACK_SERVICES = ('s3',)


@dataclass(frozen=True)
class LocalstackS3Resources:
    bucket: str
    endpoint_url: str
    region: str


@pytest.fixture(scope='session')
def localstack_s3() -> Generator[LocalstackS3Resources, None, None]:
    """
    Provide an S3 bucket backed by LocalStack and temporarily point AWS settings/env to it.

    - Starts a LocalStack container with S3 enabled
    - Creates a test bucket
    - Overrides `settings.aws` and corresponding environment variables
    - Restores configuration and stops the container after the test session
    """
    container = LocalStackContainer(image=LOCALSTACK_IMAGE).with_services(*LOCALSTACK_SERVICES)

    settings = get_settings()
    aws_settings = settings.aws
    saved_attrs = {
        'access_key_id': aws_settings.access_key_id,
        'secret_access_key': aws_settings.secret_access_key,
        'region': aws_settings.region,
        's3_bucket': aws_settings.s3_bucket,
        'endpoint_url': getattr(aws_settings, 'endpoint_url', None),
    }
    saved_env = {
        'AWS__ACCESS_KEY_ID': os.environ.get('AWS__ACCESS_KEY_ID'),
        'AWS__SECRET_ACCESS_KEY': os.environ.get('AWS__SECRET_ACCESS_KEY'),
        'AWS__REGION': os.environ.get('AWS__REGION'),
        'AWS__S3_BUCKET': os.environ.get('AWS__S3_BUCKET'),
        'AWS__ENDPOINT_URL': os.environ.get('AWS__ENDPOINT_URL'),
    }

    resources: LocalstackS3Resources | None = None
    try:
        container.start()
        s3_client = container.get_client('s3')

        endpoint_url = container.get_url()

        bucket_kwargs: dict[str, Any] = {'Bucket': LOCALSTACK_S3_BUCKET}
        region_constraint = container.region_name
        if region_constraint and region_constraint != 'us-east-1':
            bucket_kwargs['CreateBucketConfiguration'] = {'LocationConstraint': region_constraint}
        s3_client.create_bucket(**bucket_kwargs)

        resources = LocalstackS3Resources(
            bucket=LOCALSTACK_S3_BUCKET,
            endpoint_url=endpoint_url,
            region=container.region_name or "eu-west-1",
        )
    except Exception as exc:
        pytest.skip(f'Unable to start LocalStack S3 container: {exc}')

    assert resources is not None

    aws_settings.access_key_id = SecretStr(LOCALSTACK_ACCESS_KEY)
    aws_settings.secret_access_key = SecretStr(LOCALSTACK_SECRET_KEY)
    aws_settings.region = resources.region
    aws_settings.s3_bucket = LOCALSTACK_S3_BUCKET
    aws_settings.endpoint_url = resources.endpoint_url

    os.environ['AWS__ACCESS_KEY_ID'] = LOCALSTACK_ACCESS_KEY
    os.environ['AWS__SECRET_ACCESS_KEY'] = LOCALSTACK_SECRET_KEY
    os.environ['AWS__REGION'] = resources.region
    os.environ['AWS__S3_BUCKET'] = LOCALSTACK_S3_BUCKET
    os.environ['AWS__ENDPOINT_URL'] = resources.endpoint_url

    get_settings.cache_clear()

    try:
        yield resources
    finally:
        container.stop()
        for attr, value in saved_attrs.items():
            setattr(aws_settings, attr, value)
        for env_key, env_value in saved_env.items():
            if env_value is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = env_value
