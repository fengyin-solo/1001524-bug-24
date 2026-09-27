"""供电保障业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.store import store

MODULE = "power"
REQUIRED_FIELDS = ["供电编号", "所属站点", "供电方式"]
# 确认正常前必须补齐的字段，缺了要在接口与页面上指出来
CHECK_FIELDS = ["备电时长", "责任人员"]
STATUS_ORDER = ["待巡检", "巡检中", "供电正常", "备电不足", "已断电"]
ACTION_RULES = {"安排巡检": "巡检中", "确认正常": "供电正常", "标记断电": "已断电"}
# 备电时长低于该阈值才允许落入备电不足
MIN_BACKUP_HOURS = 4.0
PENDING_STATUSES = {"待巡检", "巡检中", "备电不足"}
ABNORMAL_STATUSES = {"备电不足"}

_DURATION_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(小时|h|H|分钟|min)?\s*$")


def parse_backup_hours(value: Any) -> float | None:
    """把备电时长解析成小时数；认不出时返回 None，由调用方指出来。"""
    if isinstance(value, (int, float)):
        return float(value)
    match = _DURATION_PATTERN.match(str(value or ""))
    if not match:
        return None
    hours = float(match.group(1))
    if match.group(2) in ("分钟", "min"):
        hours /= 60
    return hours


class PowerService:
    def _missing_fields(self, entry: dict[str, Any]) -> list[str]:
        return [field for field in CHECK_FIELDS if not str(entry.get(field) or "").strip()]

    def _present(self, entry: dict[str, Any]) -> dict[str, Any]:
        """对外输出统一口径：供电状态跟随 status，附上缺失字段与处理记录。"""
        row = dict(entry)
        row["供电状态"] = entry.get("status", "")
        row["missing_fields"] = self._missing_fields(entry)
        row["history"] = list(entry.get("history") or [])
        return row

    def _sync_flags(self, entry: dict[str, Any]) -> None:
        status = str(entry.get("status") or "")
        entry["pending"] = status in PENDING_STATUSES
        entry["abnormal"] = status in ABNORMAL_STATUSES
        entry["供电状态"] = status

    def _record(self, entry: dict[str, Any], action: str, old: str, new: str, detail: str) -> None:
        history = entry.setdefault("history", [])
        history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "from": old,
            "to": new,
            "detail": detail,
        })

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
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._present(entry) if entry is not None else None

    def stats(self) -> list[dict[str, Any]]:
        """统计卡口径：与列表、概览看板都取自同一份内存数据。"""
        rows = store.rows(MODULE)
        return [
            {"label": "在册供电单元", "value": len(rows)},
            {"label": "备电不足", "value": sum(1 for row in rows if row.get("status") == "备电不足")},
            {"label": "已断电站点", "value": sum(1 for row in rows if row.get("status") == "已断电")},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + CHECK_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        self._sync_flags(entry)
        self._record(entry, "登记", "", entry["status"], "供电单元登记入册")
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"供电单元 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于供电保障可执行范围"

        detail = f"供电单元已{action}"
        if action == "确认正常":
            missing = self._missing_fields(entry)
            if missing:
                return None, f"供电单元 {entry_id} 的{'、'.join(missing)}未填写，请先补齐再确认正常"
            hours = parse_backup_hours(entry.get("备电时长"))
            if hours is None:
                return None, f"供电单元 {entry_id} 的备电时长「{entry.get('备电时长')}」无法识别为小时数，请修正后再确认正常"
            if hours < MIN_BACKUP_HOURS:
                target = "备电不足"
                detail = f"确认完成：备电时长 {hours:g} 小时低于 {MIN_BACKUP_HOURS:g} 小时下限，标记为备电不足"
            else:
                target = "供电正常"
                detail = f"确认完成：备电时长 {hours:g} 小时满足要求，标记为供电正常"
        else:
            target = ACTION_RULES[action]

        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"

        old = str(entry.get("status") or "")
        if old == target:
            # 幂等：重复点击不来回改状态，也不重复写处理记录
            return self._present(entry), f"供电单元已处于「{target}」，本次未重复变更"

        entry["status"] = target
        self._sync_flags(entry)
        self._record(entry, action, old, target, detail)
        return self._present(entry), detail
