from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.time_utils import utc_now
from app.db.models import ChatMessage, Round


SUMMARY_LINE_MAX_CHARS = 180


@dataclass
class RoundConversationContext:
    conversation_summary: str | None
    last_summarized_message_id: str | None
    summary_updated_at: datetime | None
    total_message_count: int
    recent_message_count: int
    summarized_message_count: int
    recent_messages: list[ChatMessage]


def _trim_text(text: str, max_chars: int = SUMMARY_LINE_MAX_CHARS) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def _display_role(role: str) -> str:
    if role == "user":
        return "사용자"
    if role == "ai":
        return "AI"
    return role


def render_conversation_summary(messages: list[ChatMessage]) -> str | None:
    if not messages:
        return None

    summary_lines = [f"이전 대화 요약 ({len(messages)}개 메시지)"]
    for message in messages:
        summary_lines.append(f"- {_display_role(message.role)}: {_trim_text(message.content)}")
    return "\n".join(summary_lines)


def build_round_conversation_context(
    *,
    messages: list[ChatMessage],
    recent_message_limit: int,
    summary_updated_at: datetime | None = None,
) -> RoundConversationContext:
    limit = max(1, int(recent_message_limit or 1))
    total_message_count = len(messages)

    summarized_messages = messages[:-limit] if total_message_count > limit else []
    recent_messages = list(messages[-limit:]) if messages else []
    conversation_summary = render_conversation_summary(summarized_messages)

    return RoundConversationContext(
        conversation_summary=conversation_summary,
        last_summarized_message_id=str(summarized_messages[-1].message_id) if summarized_messages else None,
        summary_updated_at=summary_updated_at if conversation_summary else None,
        total_message_count=total_message_count,
        recent_message_count=len(recent_messages),
        summarized_message_count=len(summarized_messages),
        recent_messages=recent_messages,
    )


def sync_round_conversation_context(
    *,
    round_obj: Round,
    messages: list[ChatMessage],
    recent_message_limit: int,
) -> RoundConversationContext:
    current_context = build_round_conversation_context(
        messages=messages,
        recent_message_limit=recent_message_limit,
        summary_updated_at=round_obj.summary_updated_at,
    )

    next_summary = current_context.conversation_summary
    next_last_message_id = messages[:-max(1, int(recent_message_limit or 1))][-1].message_id if len(messages) > max(1, int(recent_message_limit or 1)) else None

    summary_changed = (round_obj.conversation_summary or None) != next_summary
    last_message_changed = round_obj.last_summarized_message_id != next_last_message_id

    if summary_changed or last_message_changed:
        round_obj.conversation_summary = next_summary
        round_obj.last_summarized_message_id = next_last_message_id
        round_obj.summary_updated_at = utc_now() if next_summary else None
        current_context.summary_updated_at = round_obj.summary_updated_at

    return current_context
