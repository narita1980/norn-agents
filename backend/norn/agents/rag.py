"""Skuld RAG スタブ — 学習リソースのキーワード検索。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from norn.db.models import LearningResource

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# 初回起動用の組み込みカタログ（DB 空のとき seed 相当）
_BUILTIN_RESOURCES: tuple[tuple[str, str, str, str], ...] = (
    (
        "Python asyncio 公式ドキュメント",
        "https://docs.python.org/3/library/asyncio.html",
        "非同期 I/O の基礎とベストプラクティス",
        "async,python,concurrency",
    ),
    (
        "FastAPI 公式チュートリアル",
        "https://fastapi.tiangolo.com/tutorial/",
        "Web API 設計と型ヒントの実践",
        "fastapi,python,api",
    ),
    (
        "SQLAlchemy 2.0 非同期ガイド",
        "https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html",
        "async/await 対応 ORM の使い方",
        "sqlalchemy,async,database",
    ),
    (
        "テスト駆動開発入門",
        "https://docs.pytest.org/en/stable/getting-started.html",
        "pytest による単体テストの書き方",
        "test,pytest,quality",
    ),
    (
        "セキュアコーディング OWASP Top 10",
        "https://owasp.org/www-project-top-ten/",
        "Web アプリの代表的な脆弱性と対策",
        "security,owasp",
    ),
    (
        "リファクタリング入門",
        "https://refactoring.guru/refactoring",
        "コード smell と改善パターン",
        "refactoring,design,clean-code",
    ),
)


async def ensure_learning_resources(session: AsyncSession) -> None:
    from sqlalchemy import func

    count = await session.scalar(select(func.count()).select_from(LearningResource))
    if count and int(count) > 0:
        return
    for title, url, description, tags in _BUILTIN_RESOURCES:
        session.add(LearningResource(title=title, url=url, description=description, tags=tags))
    await session.flush()


async def search_learning_resources(
    session: AsyncSession,
    weak_areas: list[str] | None,
    *,
    limit: int = 3,
) -> str:
    """弱点キーワードに基づき学習リソースを検索し、プロンプト用テキストを返す。"""
    await ensure_learning_resources(session)
    keywords = _extract_keywords(weak_areas or [])
    stmt = select(LearningResource).limit(50)
    rows = list((await session.execute(stmt)).scalars().all())
    if not rows:
        return ""

    scored: list[tuple[int, LearningResource]] = []
    for row in rows:
        score = _score_resource(row, keywords)
        if score > 0 or not keywords:
            scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored and rows:
        scored = [(0, r) for r in rows[:limit]]

    lines: list[str] = []
    for _, resource in scored[:limit]:
        lines.append(f"- {resource.title}: {resource.url}\n  {resource.description[:120]}")
    if not lines:
        return ""
    return "# 関連する学習リソース（スクルド向け）\n" + "\n".join(lines)


def _extract_keywords(weak_areas: list[str]) -> list[str]:
    keywords: list[str] = []
    mapping = {
        "async": ["async", "await", "非同期"],
        "test": ["test", "テスト", "pytest"],
        "security": ["security", "セキュリ", "脆弱"],
        "sql": ["sql", "database", "db", "クエリ"],
        "api": ["api", "rest", "endpoint"],
        "type": ["型", "type", "hint"],
        "refactor": ["リファクタ", "refactor", "設計"],
    }
    text = " ".join(weak_areas).lower()
    for key, hints in mapping.items():
        if any(h in text for h in hints):
            keywords.append(key)
    return keywords


def _score_resource(resource: LearningResource, keywords: list[str]) -> int:
    if not keywords:
        return 0
    haystack = f"{resource.title} {resource.description} {resource.tags}".lower()
    return sum(1 for kw in keywords if kw in haystack)
