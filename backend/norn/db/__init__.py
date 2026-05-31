"""DB レイヤ。SQLAlchemy 2.x async + Alembic ベース。

公開する API は最小:
    - get_session: FastAPI Depends 用の AsyncSession ジェネレータ
    - init_models: 開発便宜の create_all（本番は Alembic）
    - reset_engine_cache: テスト用、Settings 差し替え後に呼ぶ
    - models: Base, ReviewSession, AgentConversation, ChatMessage
    - repositories: 各 async 関数
"""

from norn.db.engine import get_session, init_models, reset_engine_cache, session_scope
from norn.db.models import (
    AgentConversation,
    Base,
    ChatMessage,
    ReviewSession,
    User,
)

__all__ = [
    "AgentConversation",
    "Base",
    "ChatMessage",
    "ReviewSession",
    "User",
    "get_session",
    "init_models",
    "reset_engine_cache",
    "session_scope",
]
