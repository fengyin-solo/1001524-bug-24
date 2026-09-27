"""供电保障业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.store import store

MODULE = "power"
REQUIRED_FIELDS = ["供电编号", "所属站点", "供电方式"]
STATUS_ORDER = ["待巡检", "巡检中", "供电正常", "备电不足", "已断电"]

# 备电时长低于该阈值（小时）即判定备电不足
BACKUP_MIN_HOURS = 4.0
# 确认正常前必须补齐的字段，缺了要在结果里指出来
CONFIRM_REQUIRED_FIELDS = ["备电时长", "责任人员"]

# 待处理口径：还没得出结论的状态；异常口径：备电不足。概览看板与统计卡共用这一份口径。
PENDING_STATUSES = {"待巡检", "巡检中"}
ABNORMAL_STATUSES = {"备电不足"}

# 每个动作允许从哪些源状态发起；目标态为 None 表示由业务规则评估得出
ACTION_TRANSITIONS: dict[str, dict[str, Any]] = {
    "安排巡检": {"from": {"待巡检", "供电正常", "备电不足"}, "to": "巡检中"},
    "确认正常": {"from": {"待巡检", "巡检中", "备电不足"}, "to": None},
    "标记断电": {"from": {"待巡检", "巡检中", "供电正常", "备电不足"}, "to": "已断电"},
}


def _parse_hours(value: Any) -> float | None:
    """从「6」「6小时」「6.5h」这类写法里取出小时数；取不到视为无法识别。"""
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match else None


class PowerService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("供电编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def stats(self) -> dict[str, int]:
        """统计卡口径：与列表、概览看板共用同一份状态数据。"""
        rows = store.rows(MODULE)
        return {
            "在册供电单元": len(rows),
            "备电不足": sum(1 for row in rows if row.get("status") == "备电不足"),
            "已断电站点": sum(1 for row in rows if row.get("status") == "已断电"),
        }

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in ("蓄电池容量", "上次放电测试", "备电时长", "责任人员"):
            if values.get(field) is not None:
                entry[field] = values.get(field)
        self._apply_status(entry, STATUS_ORDER[0])
        entry["history"] = [self._record("登记", f"— → {STATUS_ORDER[0]}", "供电单元登记入库")]
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"供电单元 {entry_id} 不存在或已归档"
        rule = ACTION_TRANSITIONS.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于供电保障可执行范围"
        current = str(entry.get("status") or STATUS_ORDER[0])

        if action == "确认正常" and current == "供电正常":
            # 幂等：已确认正常的重复点击不改状态、不重复记处理记录
            return entry, "供电单元已处于「供电正常」，无需重复确认正常"
        if current not in rule["from"]:
            return None, f"当前状态「{current}」不允许执行「{action}」"

        if action == "确认正常":
            missing = [field for field in CONFIRM_REQUIRED_FIELDS if not str(entry.get(field) or "").strip()]
            if missing:
                return None, f"请先补齐：{'、'.join(missing)}"
            hours = _parse_hours(entry.get("备电时长"))
            if hours is None:
                return None, "备电时长无法识别，请按小时数填写（如 6 或 6小时）"
            if hours >= BACKUP_MIN_HOURS:
                target = "供电正常"
                reason = f"备电时长 {hours:g} 小时，不低于 {BACKUP_MIN_HOURS:g} 小时阈值"
            else:
                target = "备电不足"
                reason = f"备电时长 {hours:g} 小时，低于 {BACKUP_MIN_HOURS:g} 小时阈值"
            if current == target:
                # 评估结论与现状一致：只提示，不重复记处理记录
                return entry, f"{reason}，仍为{target}"
            note = f"{reason}，确认{target}" if target == "供电正常" else f"{reason}，判定{target}"
        else:
            target = str(rule["to"])
            if current == target:
                return entry, f"供电单元已处于「{target}」，无需重复{action}"
            note = f"供电单元已{action}"

        self._apply_status(entry, target)
        entry.setdefault("history", []).append(
            self._record(action, f"{current} → {target}", note)
        )
        return entry, note

    def _apply_status(self, entry: dict[str, Any], status: str) -> None:
        """状态、业务字段与统计口径一起落，避免列表里状态标记错位。"""
        entry["status"] = status
        entry["供电状态"] = status
        entry["pending"] = status in PENDING_STATUSES
        entry["abnormal"] = status in ABNORMAL_STATUSES

    def _record(self, action: str, change: str, note: str) -> dict[str, str]:
        return {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "动作": action,
            "状态变化": change,
            "说明": note,
        }
