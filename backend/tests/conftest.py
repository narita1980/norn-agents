import hashlib
import hmac
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from norn.api.main import create_app
from norn.api.routes.chat import _reset_threads_for_tests
from norn.config import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"

TEST_GITHUB_SECRET = "testsecret"


@pytest.fixture
def settings_test() -> Settings:
    return Settings(
        github_webhook_secret=TEST_GITHUB_SECRET,
        azure_openai_api_key="dummy",
        azure_openai_endpoint="https://dummy.openai.azure.com",
        azure_openai_deployment="dummy-deployment",
        log_level="WARNING",
        payload_size_limit_bytes=2048,
    )


@pytest.fixture
def app(settings_test: Settings):
    application = create_app(settings=settings_test)
    yield application
    _reset_threads_for_tests()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def github_signature():
    def _sign(body: bytes, secret: str = TEST_GITHUB_SECRET) -> str:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    return _sign


@pytest.fixture
def github_ping_payload() -> bytes:
    return (FIXTURES_DIR / "github_ping.json").read_bytes()


@pytest.fixture
def github_pull_request_payload() -> bytes:
    return (FIXTURES_DIR / "github_pull_request.json").read_bytes()


@pytest.fixture
def github_pull_request_non_draft_payload() -> bytes:
    return (FIXTURES_DIR / "github_pull_request_non_draft.json").read_bytes()


@pytest.fixture
def parsed_pull_request(github_pull_request_payload: bytes) -> dict:
    return json.loads(github_pull_request_payload)
