"""管理用 CLI。例: uv run python -m norn.cli create-user --username norn --password secret"""

from __future__ import annotations

import argparse
import asyncio
import sys

from norn.auth.demo import DEMO_TEST_USER_PASSWORD
from norn.config import get_settings
from norn.db import init_models, reset_engine_cache, session_scope
from norn.db.users import create_user, seed_test_users


async def _cmd_create_user(username: str, password: str) -> int:
    settings = get_settings()
    reset_engine_cache()
    if settings.database_url.startswith("sqlite"):
        await init_models(database_url=settings.database_url)
    try:
        async with session_scope() as db:
            await create_user(db, username=username, password=password)
            await db.commit()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"created user: {username.strip()}")
    return 0


async def _cmd_seed_test_users(password: str) -> int:
    settings = get_settings()
    reset_engine_cache()
    if settings.database_url.startswith("sqlite"):
        await init_models(database_url=settings.database_url)
    async with session_scope() as db:
        lines = await seed_test_users(db, password=password)
        await db.commit()
    for line in lines:
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="norn.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user", help="Create a login user in the database")
    create.add_argument("--username", required=True)
    create.add_argument("--password", required=True)

    seed = sub.add_parser(
        "seed-test-users",
        help="Create demo login users (yuki/takeshi/sakura) idempotently",
    )
    seed.add_argument(
        "--password",
        default=DEMO_TEST_USER_PASSWORD,
        help=f"Shared password for all demo users (default: {DEMO_TEST_USER_PASSWORD})",
    )

    args = parser.parse_args(argv)
    if args.command == "create-user":
        return asyncio.run(_cmd_create_user(args.username, args.password))
    if args.command == "seed-test-users":
        return asyncio.run(_cmd_seed_test_users(args.password))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
