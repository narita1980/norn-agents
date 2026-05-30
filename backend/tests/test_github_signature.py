import hashlib
import hmac

from norn.api.signatures.github import verify_github_signature

SECRET = "supersecret"
BODY = b'{"hello": "world"}'


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_returns_true() -> None:
    assert verify_github_signature(SECRET, BODY, _sign(BODY)) is True


def test_tampered_body_returns_false() -> None:
    sig = _sign(BODY)
    assert verify_github_signature(SECRET, BODY + b"x", sig) is False


def test_wrong_secret_returns_false() -> None:
    sig = _sign(BODY, "othersecret")
    assert verify_github_signature(SECRET, BODY, sig) is False


def test_missing_header_returns_false() -> None:
    assert verify_github_signature(SECRET, BODY, None) is False
    assert verify_github_signature(SECRET, BODY, "") is False


def test_header_without_sha256_prefix_returns_false() -> None:
    sig_no_prefix = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    assert verify_github_signature(SECRET, BODY, sig_no_prefix) is False
    assert verify_github_signature(SECRET, BODY, "sha1=" + sig_no_prefix) is False


def test_empty_secret_returns_false() -> None:
    assert verify_github_signature("", BODY, _sign(BODY)) is False


def test_uses_constant_time_compare(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    original = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return original(a, b)

    monkeypatch.setattr("norn.api.signatures.github.hmac.compare_digest", spy)
    verify_github_signature(SECRET, BODY, _sign(BODY))
    assert len(calls) == 1
