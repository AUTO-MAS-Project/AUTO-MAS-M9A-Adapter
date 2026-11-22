#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""M9A 专项插件：登记 M9A 托管与账号类型，向项目更新登记托管属主 ``m9a_adapter``。

托管生命周期钩子（保存前整理与加密、读账号前与新账号补默认队列、复制托管带视图、删除托管清视图）、
按配置判定游戏类型与桌面分身都转调 ``lifecycle``；有运行没结束时 ``teardown_blockers`` 拒绝停用。

规则 L：本模块和它顶层的整条导入链里不出现别的插件包（三块积木、另外两个专项）；跨插件的导入
都写在函数体内。两块库（``maafw_interface``、``maafw_native``）不受此限。
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from auto_mas_core import Config, ScriptAdapterPlugin, ScriptTypeDecl, TaskMode
from auto_mas_core.host.utils import get_logger

from . import lifecycle
from .config import M9AConfig, M9AUserConfig
from .expander import M9AExpander, _prefetch_check, active_runs

# 同一个开发版 SDK 号码同时出现在让位前后的宿主：宿主仍内置 M9A 时拒绝加载，避免同名类型冲突。
_builtin = Config.ScriptConfig.entry_types.get("M9AConfig")
if _builtin is not None and _builtin.__module__.startswith("app."):
    raise ImportError("当前 AUTO-MAS 仍内置 MFW / M9A / MSS，请换到让位分支")

logger = get_logger("M9A 专项插件")

# 属主名沿用内置时的 ``m9a_adapter``：视图目录、导入报告里记的属主不变
M9A_OWNER = "m9a_adapter"
OWNER_SERVICE = "maafw.owner.m9a_adapter.v1"
PROJECT_SERVICE = "maafw.project.v1"

# 当前启用实例的属主入口；管理器经 ``_resolve_owner`` 每次现取
_owner: Any = None


def _resolve_owner() -> Any:
    """M9A 的托管属主入口（``BuiltinConfigOwner``）；插件没启用时没有。"""

    if _owner is None:
        raise RuntimeError("M9A 专项插件未启用，取不到托管属主入口")
    return _owner


def _project_mismatch(interface: Any) -> str | None:
    """M9A 托管要换进来的项目不是 M9A 项目时给用户看的拒收原因；能收或识别出错时返回 None。"""

    from .rules import TYPE_KEY, is_m9a_project

    try:
        if is_m9a_project(interface):
            return None
    except Exception as exc:  # noqa: BLE001 - 识别出错不该挡住导入
        logger.warning(f"MaaFW 特调 {TYPE_KEY} 识别项目失败，不拦截：{exc}")
        return None
    return f"这不是 {TYPE_KEY} 项目。要用别的项目，请新建通用 MFW 托管。"


def _optional_decl_fields(**fields: Callable[..., Any]) -> dict[str, Any]:
    """``ScriptTypeDecl`` 里较新的可选项（按配置判定游戏类型、桌面分身）：宿主的声明类有这一项才传。

    同一个 SDK 版本号同时出现在带与不带这些出口的宿主上，没法靠依赖下限区分；旧宿主上不传，行为同 0.1.0。
    """

    known = {field.name for field in dataclasses.fields(ScriptTypeDecl)}
    return {name: value for name, value in fields.items() if name in known}


class Plugin(ScriptAdapterPlugin):
    script_type_key = "M9A"
    requires = ("maafw.agent_env.v1", "maafw.runner.v1", PROJECT_SERVICE)
    provides_services = {OWNER_SERVICE: "owner_entry"}
    decl = ScriptTypeDecl(
        script_type=M9AConfig,
        user_type=M9AUserConfig,
        expander_class=M9AExpander,
        plan_type=None,
        supported_modes=(TaskMode.AUTO_PROXY,),
        prefetch_check=_prefetch_check,
        game_kinds=("emulator", "client"),
        supports_mod_avd=True,
        activity_game="reverse1999",
        **_optional_decl_fields(
            game_kind=lifecycle.game_kind,
            desktop_session=lifecycle.desktop_session,
        ),
    )

    def __init__(self, config: Any = None, record: Any = None) -> None:
        super().__init__(config=config, record=record)
        self._owner: Any = None

    async def pre_enable(self) -> None:
        refs = {
            "PlanConfig": Config.PlanConfig,
            "games": Config.GameConfig,
            "ScriptConfig": Config.ScriptConfig,
        }
        M9AConfig.related_config = refs
        M9AUserConfig.related_config = refs

    async def on_enable(self) -> None:
        global _owner
        # 属主入口在专项共用库里；它用到项目更新的属主协议数据类时才取（规则 L）
        from maafw_adapter_kit.owner_entry import BuiltinConfigOwner

        from .rules import M9A_PLAN_RULES

        self._owner = BuiltinConfigOwner(
            M9A_OWNER,
            lambda: M9AConfig,
            plan_rules=M9A_PLAN_RULES,
            project_mismatch=_project_mismatch,
        )
        _owner = self._owner
        project = self.services.require(PROJECT_SERVICE)
        await project("owner.register", name=M9A_OWNER, service=OWNER_SERVICE)

    async def on_disable(self) -> None:
        global _owner
        try:
            project = self.services.get(PROJECT_SERVICE)
            if project is not None:
                await project("owner.unregister", name=M9A_OWNER)
        except Exception as exc:  # noqa: BLE001 - 注销失败不挡停用
            logger.warning(f"M9A 专项注销托管属主失败：{exc}")
        finally:
            if _owner is self._owner:
                _owner = None
            self._owner = None

    def owner_entry(self) -> Any:
        """属主服务 ``maafw.owner.m9a_adapter.v1``：返回属主入口对象。"""

        return self._owner

    async def teardown_blockers(self) -> list[str]:
        """有 M9A 运行没结束时拒绝停用、重载、卸载（宿主还会另查托管锁）。"""

        count = active_runs()
        return [f"有 {count} 个 M9A 托管的运行还没结束"] if count else []

    # ── 托管生命周期钩子（宿主带这组出口时才会调；做的事见 ``lifecycle``） ──

    async def prepare_user_update(
        self, script: Any, user: Any, data: dict[str, Any]
    ) -> None:
        """保存账号前：整理受管任务（启动 / 切号 / 关闭）再加密密码。"""

        await lifecycle.prepare_user_update(script, user, data)

    async def prepare_user_read(self, script: Any, user_ids: list[str] | None) -> None:
        """读账号前：空任务队列按项目默认补上。"""

        await lifecycle.prepare_user_read(script, user_ids)

    async def on_user_added(self, script: Any, user: Any) -> None:
        """新建账号后：空任务队列按项目默认写入。"""

        await lifecycle.on_user_added(script, user)

    async def on_script_cloned(self, source: Any, target: Any) -> None:
        """复制托管：给新托管物化项目视图（记 M9A 属主）。"""

        await lifecycle.on_script_cloned(source, target, owner=M9A_OWNER)

    async def on_script_removed(self, script_id: str) -> None:
        """删除托管：当场删掉它的项目视图，起一轮运行池对账。"""

        await lifecycle.on_script_removed(script_id, owner=M9A_OWNER)


__all__ = ["M9A_OWNER", "OWNER_SERVICE", "Plugin"]
