import json
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status

from norn.api.signatures.github import verify_github_signature
from norn.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def verified_github_payload(
    request: Request,
    settings: SettingsDep,
) -> dict[str, Any]:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(settings.github_webhook_secret, body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")

    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid JSON payload",
        ) from exc
