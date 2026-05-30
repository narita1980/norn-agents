import hashlib
import hmac


def verify_github_signature(
    secret: str,
    body: bytes,
    signature_header: str | None,
) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    if not secret:
        return False

    received = signature_header.removeprefix("sha256=")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)
