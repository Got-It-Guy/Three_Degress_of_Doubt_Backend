from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.time_utils import utc_now
from app.db.models import Round, Scenario, Stage, UserStageProgress
from app.services.progress_policy import has_stage_clear_record
from app.services.reports import upsert_round_report


@dataclass
class JudgeResult:
    result: str
    score_delta: int
    current_score: int
    current_warning: int
    is_stage_cleared: bool


def judge_round(
    *,
    db: Session,
    round_obj: Round,
    progress: UserStageProgress,
    stage: Stage,
    scenario: Scenario,
    is_fraud_judged: bool,
) -> JudgeResult:
    judged_at = utc_now()

    passed = False
    if is_fraud_judged:
        passed = scenario.is_fraud and round_obj.evidence_count >= scenario.min_evidence_count
    else:
        passed = not scenario.is_fraud

    if passed:
        round_obj.is_fraud_judged = is_fraud_judged
        round_obj.judged_at = judged_at
        round_obj.status = "judged"
        round_obj.ended_at = judged_at
        progress.stage_score += 1
        response_score = progress.stage_score
        round_obj.result = "pass"
        round_obj.score_delta = 1
        attempt_cleared = response_score >= stage.required_score
        if attempt_cleared:
            progress.is_cleared = True
            if progress.cleared_at is None:
                progress.cleared_at = round_obj.ended_at
            if progress.best_round_count is None:
                progress.best_round_count = progress.total_round_count
            else:
                progress.best_round_count = min(progress.best_round_count, progress.total_round_count)

        # PDF only documents report availability for pass/report, but it also defines false_alarm.
        # To keep the frontend usable, a false_alarm report is generated for a normal scenario pass.
        report_type = "fraud_found" if scenario.is_fraud else "false_alarm"
        upsert_round_report(db=db, round_obj=round_obj, scenario=scenario, report_type=report_type)

        progress.updated_at = utc_now()
        db.flush()
        return JudgeResult(
            result="pass",
            score_delta=1,
            current_score=response_score,
            current_warning=progress.warning_count,
            is_stage_cleared=attempt_cleared,
        )

    progress.warning_count += 1
    round_obj.score_delta = 0

    if scenario.is_fraud and not is_fraud_judged:
        upsert_round_report(db=db, round_obj=round_obj, scenario=scenario, report_type="fraud_missed")

    if not scenario.is_fraud and is_fraud_judged:
        upsert_round_report(db=db, round_obj=round_obj, scenario=scenario, report_type="false_alarm")

    if progress.warning_count >= 2:
        round_obj.is_fraud_judged = is_fraud_judged
        round_obj.judged_at = judged_at
        round_obj.status = "judged"
        round_obj.ended_at = judged_at
        progress.stage_score = 0
        progress.warning_count = 0
        if has_stage_clear_record(progress):
            progress.is_cleared = True
        round_obj.result = "reset"
        progress.updated_at = utc_now()
        db.flush()
        return JudgeResult(
            result="reset",
            score_delta=0,
            current_score=progress.stage_score,
            current_warning=progress.warning_count,
            is_stage_cleared=False,
        )

    # A first wrong judgement is a warning inside the same round, not a final judgement.
    # The round stays in progress so the user gets one more chance.
    round_obj.is_fraud_judged = None
    round_obj.judged_at = None
    round_obj.status = "in_progress"
    round_obj.ended_at = None
    round_obj.result = "warning"
    progress.updated_at = utc_now()
    db.flush()
    return JudgeResult(
        result="warning",
        score_delta=0,
        current_score=progress.stage_score,
        current_warning=progress.warning_count,
        is_stage_cleared=False,
    )
