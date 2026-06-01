"""エンジニアレベル別の応答方針。

チャット UI のテスト用ペルソナ切替と、合議プロンプトへの注入に使う。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

UserLevel = Literal["junior", "mid", "senior"]

# frontend/src/lib/userLevels.ts LOGIN_USERNAME_BY_LEVEL と同期
TEST_LOGIN_USERS: dict[UserLevel, str] = {
    "junior": "yuki",
    "mid": "takeshi",
    "senior": "sakura",
}


@dataclass(frozen=True)
class LevelProfile:
    level: UserLevel
    label: str
    profile: str
    response_guidelines: str


USER_LEVELS: dict[UserLevel, LevelProfile] = {
    "junior": LevelProfile(
        level="junior",
        label="若手（入社1年目・初学者）",
        profile="Python / Web 開発を学び始めたばかり。専門用語や設計の背景が分からないことが多い。",
        response_guidelines=(
            "  - 専門用語には短い補足を添える（括弧書きで OK）。\n"
            "  - 指摘は 1 つずつ、**小さな次の一手**に分解する。\n"
            "  - must_fix / next_pr は合計 3 件以内を目安にし、優先度の高いものだけ。\n"
            "  - 励ましと具体例を多めに。前提知識は説明してから本題へ。"
        ),
    ),
    "mid": LevelProfile(
        level="mid",
        label="中級（3年目・実務経験あり）",
        profile="機能開発の経験があり、基本的な設計・テストは理解している。",
        response_guidelines=(
            "  - 用語説明は最小限。実装への落とし込みを中心に。\n"
            "  - 指摘は優先度付きでバランスよく（現行の Norns 標準トーン）。\n"
            "  - トレードオフがあれば 1 行で触れる。"
        ),
    ),
    "senior": LevelProfile(
        level="senior",
        label="上級（5年目・設計・レビュー経験あり）",
        profile="設計判断やレビュー経験があり、基本的事項の説明は不要。",
        response_guidelines=(
            "  - 冗長な説明・初歩的な用語解説は省略。\n"
            "  - 設計トレードオフ、保守性、運用・スケールの観点を厚めに。\n"
            "  - 指摘は簡潔に。代替案や判断基準を示す。\n"
            "  - 過度な励ましや手取り足取りのステップは避ける。"
        ),
    ),
}


def get_level_profile(level: UserLevel) -> LevelProfile:
    return USER_LEVELS[level]


def render_user_level_block(level: UserLevel) -> str:
    profile = get_level_profile(level)
    return (
        f"# 対象エンジニアのレベル\n"
        f"- レベル: {profile.label}\n"
        f"- プロフィール: {profile.profile}\n"
        f"- 応答方針:\n{profile.response_guidelines}"
    )
