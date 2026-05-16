from typing import Optional

from app.schemas.base import ApiBaseModel


class StageListItem(ApiBaseModel):
    stage_id: int
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_random: bool
    stage_score: int
    warning_count: int
    total_round_count: int
    is_cleared: bool


class StageListResponse(ApiBaseModel):
    status: str = "success"
    stages: list[StageListItem]


class StageEnterResponse(ApiBaseModel):
    status: str = "success"
    progress_id: str
    stage_id: int
    stage_score: int
    warning_count: int
    is_cleared: bool
    total_round_count: int
    has_incomplete_round: bool


class RoundStartData(ApiBaseModel):
    round_id: str
    scenario_id: str
    situation_prompt: str
    ai_name: str
    ai_image_url: Optional[str] = None
    started_at: str


class RoundStartResponse(ApiBaseModel):
    status: str = "success"
    message: str = "라운드가 성공적으로 생성되었습니다."
    data: RoundStartData


class StageRoundItem(ApiBaseModel):
    round_id: str
    scenario_id: str
    scenario_title: str
    is_fraud_scenario: bool
    status: str
    is_fraud_judged: Optional[bool] = None
    evidence_count: int
    result: Optional[str] = None
    score_delta: Optional[int] = None
    started_at: str
    ended_at: Optional[str] = None


class StageRoundsResponse(ApiBaseModel):
    status: str = "success"
    stage_id: int
    rounds: list[StageRoundItem]