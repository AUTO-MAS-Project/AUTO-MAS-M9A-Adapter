#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""M9A 托管的生命周期钩子与按配置的托管声明（``plugin.Plugin`` 的钩子与 ``decl`` 转调这里）。

内置时这些事由宿主的配置回调做（``build_maafw_config_handler`` + M9A 换掉的保存前准备）；插件形态下宿主经
``ScriptAdapterPlugin`` 的五个托管生命周期钩子、``ScriptTypeDecl.game_kind`` / ``desktop_session`` 调进来，
做的事与内置时逐项相同：

- 保存账号前：整理受管任务（启动 / 切号 / 关闭）再加密密码（``config_hooks.prepare_m9a_user_update``）；
- 读账号前、新建账号后：空任务队列按项目默认写成实打实的队列（``default_snapshot``）；
- 复制托管：从源托管挂着的载荷给新托管物化视图，新视图记 M9A 属主；失败留给运行前重建；
- 删除托管：当场删掉它的视图（视图记着别的属主时不删），再起一轮运行池对账；
- 游戏类型：托管显式选的 controller 是 ADB 就是模拟器，否则是客户端；判断不了返回 ``None``；
- 桌面分身：实际生效的 controller 是 Win32 才支持。

规则 L：本模块顶层只导入标准库；积木（``maafw_project_update``）和库都在函数体内取，``plugin.py`` 顶层
导入本模块不会把别的插件带进来。
"""

from __future__ import annotations

import asyncio
from typing import Any


def _logger() -> Any:
    from auto_mas_core.host.utils import get_logger

    # 与宿主内置时的托管复制 / 删除日志同名
    return get_logger("配置管理")


async def prepare_user_update(script: Any, user: Any, data: dict[str, Any]) -> None:
    """保存账号前原地准备 ``data``：整理受管任务、加密密码（只在补丁带 ``Task.TaskSnapshot`` 时）。"""

    from m9a_adapter.config_hooks import prepare_m9a_user_update

    await prepare_m9a_user_update(script, user, data=data)


async def prepare_user_read(script: Any, user_ids: list[str] | None) -> None:
    """读账号前：这些账号（``None`` 为全部）里任务队列为空的，按项目默认补上。从不抛出。"""

    from m9a_adapter import config_view

    await config_view.fill_default_snapshots(
        str(config_view.script_uid(script)), script, user_ids=user_ids
    )


async def on_user_added(script: Any, user: Any) -> None:
    """新账号：空队列按项目默认写回；项目还没导入时留到读取、运行前再补。"""

    from m9a_adapter import config_view

    await prepare_user_read(script, [str(config_view.user_uid(user))])


async def on_script_cloned(source: Any, target: Any, *, owner: str) -> None:
    """复制托管：物化目标视图（失败只记日志，运行前会重建）。

    开发者模式不随复制继承，目标挂源原渠道组的 latest；组里没有正式载荷、或源是源码形态时先不建视图，
    首次运行按来源目录导入。新视图当场记下属主 ``owner``。
    """

    from maafw_native.layout import view_dir
    from maafw_project_update.host.embedded_project import (
        FollowSourceCloneUnavailable,
        clone_embedded_copy,
        is_source_form,
    )
    from maafw_project_update.host.project_path import (
        release_project_path,
        try_reserve_project_path,
    )

    from m9a_adapter import config_view

    logger = _logger()
    await config_view.clear_follow_source(target)
    source_id = str(config_view.script_uid(source))
    target_id = str(config_view.script_uid(target))
    group_channel = config_view.update_channel(source)
    source_form = is_source_form(source)

    target_key = await try_reserve_project_path(view_dir(target_id))
    if target_key is None:
        return
    try:
        await asyncio.to_thread(
            lambda: clone_embedded_copy(
                source_script_id=source_id,
                target_script_id=target_id,
                group_channel=group_channel,
                source_form=source_form,
                owner=owner,
            )
        )
    except FollowSourceCloneUnavailable as exc:
        logger.info(f"复制托管时先不建视图，第一次运行前按来源目录导入: {exc}")
    except Exception as exc:  # noqa: BLE001 - 失败下次运行会按来源 / 载荷重建
        logger.warning(f"复制托管时建视图失败，将按需重建: {exc}")
    finally:
        await release_project_path(target_key)


async def on_script_removed(script_id: str, *, owner: str) -> None:
    """删除托管：起运行池对账（后台），再删这个托管的视图；视图记着别的属主时不删、记一句。"""

    from maafw_native.layout import view_dir
    from maafw_project_update.host.embedded_project import remove_tree, view_owner
    from maafw_project_update.host.live_projects import reconcile_in_background

    logger = _logger()
    # 先后照内置时：删除提交后先起对账（守护线程，不拖慢删除），再清视图
    reconcile_in_background("script-deleted")
    # 视图不放在 data/<uid>/ 下（避免进入配置备份的整目录快照），宿主删数据目录时不会带走它
    embedded_copy = view_dir(script_id)
    if not embedded_copy.exists():
        return
    recorded = await asyncio.to_thread(view_owner, embedded_copy)
    if recorded is not None and recorded[0] != owner:
        logger.warning(
            f"删除托管 {script_id} 时视图记着属主 {recorded[0]}（不是 {owner}），不删: "
            f"{embedded_copy}"
        )
        return
    await asyncio.to_thread(remove_tree, embedded_copy)


def game_kind(script: Any, patch: dict[str, Any]) -> str | None:
    """托管显式选的公开 controller 决定目标类别；没选、项目没导入、读不出时返回 ``None``。"""

    from maafw_interface.interface.loader import load_interface_model_cached

    from m9a_adapter import config_view

    info = patch.get("Info") if isinstance(patch, dict) else None
    controller = (
        info.get("Controller", config_view.controller_name(script))
        if isinstance(info, dict)
        else config_view.controller_name(script)
    )
    if not controller:
        return None
    root = config_view.project_root(str(config_view.script_uid(script)), script)
    if not root.is_dir():
        return None
    interface = load_interface_model_cached(root)
    selected = next(
        (item for item in interface.controller if item.name == controller), None
    )
    if selected is None:
        return None
    return "emulator" if selected.type == "Adb" else "client"


def desktop_session(script: Any) -> bool:
    """实际生效的 controller 是 Win32 时才能在桌面分身里跑；项目没导入、读不出时不支持。"""

    from maafw_interface.interface.service import MaaFWInterfaceService
    from maafw_interface.runner.run_plan import _select_controller

    from m9a_adapter import config_view

    try:
        interface = MaaFWInterfaceService().load(
            config_view.project_root(str(config_view.script_uid(script)), script)
        )
        name, _ = config_view.run_selection(script, interface)
        return _select_controller(interface, name).type == "Win32"
    except (OSError, ValueError):
        return False


__all__ = [
    "desktop_session",
    "game_kind",
    "on_script_cloned",
    "on_script_removed",
    "on_user_added",
    "prepare_user_read",
    "prepare_user_update",
]
