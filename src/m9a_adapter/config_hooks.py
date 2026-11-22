#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""M9A 账号保存前的准备：整理受管任务（启动 / 切号 / 关闭）再加密。

- :func:`prepare_m9a_user_update`：先整理（:func:`settle_m9a_user_update`）、再加密，两步都在线程里做，先后
  与通用的 ``user_update.prepare_user_update`` 相同。由账号配置类 ``M9AUserConfig.update()`` 调用。

整理的口径是 ``managed.py`` 的规则（实现在 ``arrange.settle_m9a_snapshot``），这里只是外壳：从配置里取出
interface、生效的资源名、登录方式和账号 ``Info``，调它，再把结果并回要写的数据。配置一律经 ``config_view`` 读写。

插件 0.1.0 不带配置回调与恢复池（宿主不给插件类型绑配置回调），原来的 ``build_m9a_config_handler``、
``M9A_RESTORE_POOLS``、``restore_m9a_mas`` 不搬。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from auto_mas_core.host.utils import get_logger

# 与风味路径（``tools/embedded/flavor.sanitize_user_task_update``）同名，app.log 的检索习惯不变
logger = get_logger("MaaFW 特调")


def _settle_modules() -> tuple[Any, Any, Any]:
    """整理要用的三个模块（``config_view``、``arrange``、interface 读取）；在事件循环上先导入一次，
    线程里再取就只是查缓存。"""

    from maafw_interface.interface import loader

    from m9a_adapter import arrange, config_view

    return config_view, arrange, loader


def settle_m9a_user_update(
    script_id: str,
    script_config: Any,
    user_config: Any,
    data: dict[str, Any],
) -> bool:
    """写账号配置前：``data`` 带 ``Task.TaskSnapshot`` 时按 ``managed.py`` 整理，原地改 ``data``。

    ``data`` 是 ``{分组: {字段: 值}}``（``update_user`` 与配置恢复的形状）。快照是 JSON 串就写回
    JSON 串、是字典就写回字典；要一并改的 ``Info`` 字段并进 ``data["Info"]``。返回有没有改动。
    读不到 interface、快照解析不了都原样放行：运行期还会按同一口径再处理一遍。
    """

    config_view, arrange, loader = _settle_modules()
    task = data.get("Task")
    if not isinstance(task, dict) or "TaskSnapshot" not in task:
        return False
    raw = task["TaskSnapshot"]
    try:
        snapshot = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return False
    if not isinstance(snapshot, dict):
        return False

    try:
        root = Path(config_view.project_root(script_id, script_config))
        if not root.is_dir():
            return False
        interface_model = loader.load_interface_model_cached(root)
    except Exception as exc:  # noqa: BLE001 - 读不出 interface 不该挡住保存
        logger.debug(f"保存任务配置时读取 interface 失败，未按特调整理：{exc}")
        return False

    _, resource_name = config_view.settle_selection(script_config, interface_model)
    incoming_info = data.get("Info") if isinstance(data.get("Info"), dict) else {}
    user_info = config_view.settle_user_info(user_config, incoming_info)
    try:
        settled, info_updates = arrange.settle_m9a_snapshot(
            interface_model,
            snapshot,
            resource_name=resource_name,
            login_mode=config_view.login_mode(script_config),
            user_info=user_info,
        )
    except Exception as exc:  # noqa: BLE001 - 整理失败按原样保存
        logger.warning(f"MaaFW 特调整理任务快照失败，按原样保存：{exc}")
        return False

    changed = False
    if settled != snapshot:
        task["TaskSnapshot"] = (
            json.dumps(settled, ensure_ascii=False) if isinstance(raw, str) else settled
        )
        changed = True
    if info_updates:
        info = data.get("Info")
        if not isinstance(info, dict):
            info = data["Info"] = {}
        info.update(info_updates)
        changed = True
    return changed


async def prepare_m9a_user_update(
    script: Any, user: Any, *, data: dict[str, Any]
) -> None:
    """保存账号前原地准备快照补丁：先收归受管任务及账号，再加密任务和全局表里的密码。

    配置的 stage / commit 留在调用方（``Config.update_user``）。
    """

    task_data = data.get("Task")
    if not isinstance(task_data, dict) or "TaskSnapshot" not in task_data:
        return

    # 整理要用的模块先在事件循环上导入，线程里不冷导入
    config_view, _, _ = _settle_modules()
    script_id = str(config_view.script_uid(script))
    await asyncio.to_thread(
        settle_m9a_user_update,
        script_id=script_id,
        script_config=script,
        user_config=user,
        data=data,
    )
    task_data["TaskSnapshot"] = await asyncio.to_thread(
        config_view.seal_task_snapshot,
        script_id,
        script,
        task_data["TaskSnapshot"],
    )


__all__ = [
    "prepare_m9a_user_update",
    "settle_m9a_user_update",
]
