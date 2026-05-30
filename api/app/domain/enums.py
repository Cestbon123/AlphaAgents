from enum import StrEnum


class SelectionAction(StrEnum):
    BUY = "买入"
    WATCH = "待观察"
    DROP = "放弃"


class HoldingAction(StrEnum):
    HOLD = "继续持有"
    LET_RUN = "放飞"
    STOP_LOSS = "止损"
    CLEAR = "清仓"


class WorkflowType(StrEnum):
    SELECTION = "选股"
    HOLDING = "持股分析"
    DAILY_REVIEW = "每日复盘"
    WEEKLY_REVIEW = "每周复盘"
    RESEARCH_REPORT = "个股研究报告"


class DepositionStatus(StrEnum):
    PENDING = "待确认"
    CONFIRMED = "已确认"
    EDITED = "已编辑"
    REGENERATED = "已重新生成"
    DISCARDED = "已放弃"
