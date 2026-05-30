import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from norn.api.dependencies import verified_github_payload
from norn.config import Settings


def _build_request(body: bytes, signature: str | None) -> MagicMock:
    request = MagicMock()
    request.body = AsyncMock(return_value=body)
    headers = {}
    if signature is not None:
        headers["X-Hub-Signature-256"] = signature
    request.headers.get = headers.get
    return request


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def fake_settings() -> Settings:
    return Settings(github_webhook_secret="testsecret", azure_openai_api_key="dummy")


async def test_returns_parsed_payload(fake_settings: Settings) -> None:
    body = b'{"hello": "world"}'
    request = _build_request(body, _sign("testsecret", body))
    result = await verified_github_payload(request, fake_settings)
    assert result == {"hello": "world"}


async def test_empty_body_returns_empty_dict(fake_settings: Settings) -> None:
    body = b""
    request = _build_request(body, _sign("testsecret", body))
    result = await verified_github_payload(request, fake_settings)
    assert result == {}


async def test_invalid_signature_raises_401(fake_settings: Settings) -> None:
    body = b'{"x": 1}'
    request = _build_request(body, "sha256=" + "0" * 64)
    with pytest.raises(HTTPException) as exc:
        await verified_github_payload(request, fake_settings)
    assert exc.value.status_code == 401


async def test_malformed_json_raises_400(fake_settings: Settings) -> None:
    body = b'{"invalid": '
    request = _build_request(body, _sign("testsecret", body))
    with pytest.raises(HTTPException) as exc:
        await verified_github_payload(request, fake_settings)
    assert exc.value.status_code == 400


async def test_json_payload_round_trip(fake_settings: Settings) -> None:
    body = json.dumps({"action": "opened", "number": 42}).encode()
    request = _build_request(body, _sign("testsecret", body))
    result = await verified_github_payload(request, fake_settings)
    assert result["number"] == 42
