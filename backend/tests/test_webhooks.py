import logging

import pytest
from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_readyz_returns_ok(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200


def test_request_id_is_preserved_when_provided(client: TestClient) -> None:
    response = client.get("/healthz", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"


def test_github_ping_returns_200(
    client: TestClient, github_ping_payload: bytes, github_signature
) -> None:
    response = client.post(
        "/webhook/github",
        content=github_ping_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_ping_payload),
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": "11111111-2222-3333-4444-555555555555",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"pong": True}


def test_github_pull_request_draft_opened_dispatches(
    client: TestClient,
    github_pull_request_payload: bytes,
    github_signature,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="norn.api.routes.github")
    response = client.post(
        "/webhook/github",
        content=github_pull_request_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_pull_request_payload),
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "aaaa",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert any("draft PR opened" in record.message for record in caplog.records)


def test_github_pull_request_non_draft_is_ignored(
    client: TestClient,
    github_pull_request_non_draft_payload: bytes,
    github_signature,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="norn.api.routes.github")
    response = client.post(
        "/webhook/github",
        content=github_pull_request_non_draft_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_pull_request_non_draft_payload),
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "bbbb",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202
    assert not any("draft PR opened" in record.message for record in caplog.records)
    assert any("pull_request event ignored" in record.message for record in caplog.records)


def test_github_invalid_signature_returns_401(
    client: TestClient, github_ping_payload: bytes
) -> None:
    response = client.post(
        "/webhook/github",
        content=github_ping_payload,
        headers={
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


def test_github_missing_signature_returns_401(
    client: TestClient, github_ping_payload: bytes
) -> None:
    response = client.post(
        "/webhook/github",
        content=github_ping_payload,
        headers={
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


def test_github_unsupported_event_returns_204(
    client: TestClient, github_ping_payload: bytes, github_signature
) -> None:
    response = client.post(
        "/webhook/github",
        content=github_ping_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_ping_payload),
            "X-GitHub-Event": "issues",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 204


def test_payload_size_limit_returns_413(client: TestClient) -> None:
    oversized = b"x" * 4096
    response = client.post(
        "/webhook/github",
        content=oversized,
        headers={
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 413
