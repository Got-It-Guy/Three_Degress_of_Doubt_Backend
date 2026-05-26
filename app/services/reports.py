from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, Round, RoundReport, Scenario


def upsert_round_report(
    *,
    db: Session,
    round_obj: Round,
    scenario: Scenario,
    report_type: str,
) -> RoundReport:
    evidence_messages = [
        message for message in round_obj.messages
        if message.role == "ai" and message.is_evidence
    ]
    evidence_ids = [str(message.message_id) for message in evidence_messages]

    if report_type == "fraud_found":
        summary = "훌륭합니다! 사기 단서를 정확히 파악하셨습니다."
    elif report_type == "fraud_missed":
        summary = "이번 라운드에서는 사기 단서를 놓쳤습니다. 어디가 위험했는지 복습해 보세요."
    else:
        summary = "이번 대화는 정상 흐름에 가까웠습니다. 왜 성급한 의심이었는지 확인해 보세요."

    fraud_points: list[dict] = []
    if report_type in {"fraud_found", "fraud_missed"}:
        for message in evidence_messages:
            fraud_points.append(
                {
                    "message_id": str(message.message_id),
                    "reason": message.evidence_reason or "AI가 이 메시지를 결정적인 사기 단서로 판별했습니다.",
                    "tip": "의심스러운 송금 요구나 신원 확인 회피가 나오면 공식 채널로 재확인하세요.",
                }
            )
    elif report_type == "false_alarm":
        fraud_points = []

    report = round_obj.report
    if report is None:
        report = db.execute(
            select(RoundReport).where(RoundReport.round_id == round_obj.round_id)
        ).scalar_one_or_none()

    if report is None:
        report = RoundReport(
            round_id=round_obj.round_id,
            report_type=report_type,
            summary=summary,
            evidence_messages=evidence_ids,
            fraud_points=fraud_points,
        )
        db.add(report)
        round_obj.report = report
    else:
        report.report_type = report_type
        report.summary = summary
        report.evidence_messages = evidence_ids
        report.fraud_points = fraud_points

    db.flush()
    return report


def build_report_type_for_pass(scenario: Scenario) -> str:
    return "fraud_found" if scenario.is_fraud else "false_alarm"
