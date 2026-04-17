from app.schemas.base import ApiBaseModel


class FraudPoint(ApiBaseModel):
    message_id: str
    reason: str
    tip: str


class RoundReportResponse(ApiBaseModel):
    status: str = "success"
    report_id: str
    round_id: str
    report_type: str
    summary: str
    fraud_points: list[FraudPoint]
