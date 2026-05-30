import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response, status

from norn.api.dependencies import verified_github_payload

router = APIRouter(tags=["github"])
logger = logging.getLogger("norn.api.routes.github")

SUPPORTED_EVENTS = {"ping", "pull_request"}


@router.post("/github")
async def github_webhook(
    request: Request,
    payload: Annotated[dict[str, Any], Depends(verified_github_payload)],
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    x_github_delivery: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
) -> Response:
    request_id = getattr(request.state, "request_id", "-")
    logger.info(
        "github webhook received event=%s delivery=%s repo=%s",
        x_github_event,
        x_github_delivery,
        payload.get("repository", {}).get("full_name"),
        extra={"request_id": request_id},
    )

    if x_github_event == "ping":
        return Response(
            status_code=status.HTTP_200_OK,
            content='{"pong": true}',
            media_type="application/json",
        )

    if x_github_event not in SUPPORTED_EVENTS:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if x_github_event == "pull_request":
        action = payload.get("action")
        pr_number = payload.get("pull_request", {}).get("number")
        logger.info(
            "pull_request event action=%s pr=%s (Phase 2 will dispatch agents)",
            action,
            pr_number,
            extra={"request_id": request_id},
        )

    return Response(
        status_code=status.HTTP_202_ACCEPTED,
        content='{"accepted": true}',
        media_type="application/json",
    )
