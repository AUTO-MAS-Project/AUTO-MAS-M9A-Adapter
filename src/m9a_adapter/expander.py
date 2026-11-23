#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""M9A 的 L3 外壳：整轮交给沿用的脚本级管理器 ``manager.M9AManager``。

插件路径在建 L3 之前，L2 已经拿了托管的 X 锁（``cascade=False``）、选定了游戏会话、把预下载路径写进了
脚本节点的任务参数（管理器的运行前更新从 ``script_info.info.params`` 取）；旧路径在 L2 给管理器的几样东西
（``history``、``context``、``maintenance``、「管理器自己展开账号」标记）在这里补上，管理器以「宿主已持锁」
模式运行，不再自己拿锁。L3 自己的账号循环、``build_worker`` 都不用。

托管级检查（:meth:`M9AExpander.check`）只做一件事：项目正在更新时（项目服务 ``project_peek``）返回
``ScriptSkip``，整托管记「跳过」、不进管理器。管理器自己的运行前检查判成良性跳过（项目被占用、正在切
版本），或账号全因停服维护跳过时，同样记成 L3 的跳过，免得 L3 收尾把它写成「完成」。
"""

from __future__ import annotations

from typing import Any

from auto_mas_core import TaskMode, UserExpander

# 正在跑的 M9A 外壳（插件 ``teardown_blockers`` 据此拒绝停用）
_ACTIVE: set[Any] = set()


def active_runs() -> int:
    """正在跑的 M9A 托管数。"""

    return len(_ACTIVE)


def _script_skip_type() -> Any:
    """SDK 的 ``ScriptSkip``；旧宿主没有这个出口时为 None（那时不做 L3 级的良性跳过）。"""

    try:
        from auto_mas_core.adapters.script import ScriptSkip
    except ImportError:
        return None
    return ScriptSkip


class M9AExpander(UserExpander):
    """整轮交给沿用的脚本级管理器；L3 只做外壳。"""

    async def check(self) -> Any:
        """项目正在更新（编辑页的「执行更新」整段占着视图）时良性跳过；其余交给管理器自己的检查。"""

        ScriptSkip = _script_skip_type()
        if ScriptSkip is None:
            return None

        from maafw_adapter_kit.project_texts import SKIP_UPDATING
        from maafw_adapter_kit.services import PROJECT_PEEK, script_request

        from .services import client

        # 项目此刻在不在更新：问项目服务（project_peek，看的是这个托管的视图）
        reply = await client("外壳检查").call(
            PROJECT_PEEK, script_request(str(self.script_info.script_id))
        )
        if reply.failed:
            # 拿不到服务（项目插件已停用或重载）：原来这里不会失败，按异常往上抛，文案是那句固定话
            raise RuntimeError(reply.message)
        if reply.get("updating"):
            return ScriptSkip(SKIP_UPDATING)
        return None

    async def main_task(self) -> None:
        await self.script_info.set_state(status="运行")
        self._entered = True
        _ACTIVE.add(self)
        try:
            await self._run_manager()
        finally:
            _ACTIVE.discard(self)

    async def _run_manager(self) -> None:
        ScriptSkip = _script_skip_type()
        skipped = await self.check()
        if ScriptSkip is not None and isinstance(skipped, ScriptSkip):
            # 与宿主 UserExpander.main_task 对 ScriptSkip 的处理相同：账号记「跳过」、发 warning
            await self._skip_script(skipped.reason)
            return

        from maafw_adapter_kit.project_texts import BENIGN_SKIPS

        from .manager import M9AManager  # 规则 L：函数内导入

        manager = M9AManager(self.script_info, host_locked_config=self.script_config)
        manager.history = self.history
        manager.context = self.context
        manager.maintenance = False
        # L2 收尾时复位（app/task/script_expander.py）
        self.script_info._manager_controls_users = True
        try:
            await manager._execute_task()
            error = manager.execution.error
            if (
                error is not None
                and type(error).__name__ == "FluxdownCancelUnconfirmed"
            ):
                raise error
        finally:
            await manager.callbacks.close()
            if self.task_info.mode == TaskMode.AUTO_PROXY:
                manager.finalize_completion_details(self.script_info)
            if manager.check_result in BENIGN_SKIPS:
                # 管理器已把托管记成「跳过」、发了 warning；L3 收尾照它写，不改成「完成」
                self._skipped = manager.check_result
            elif getattr(self.script_info.info, "status", None) == "跳过":
                # 账号全因停服维护跳过：管理器记了托管「跳过」，同样别让 L3 收尾改成「完成」
                self._skipped = "跳过"

    def build_worker(self, user: Any, config: Any) -> Any:
        raise NotImplementedError("由 main_task 整轮交给管理器")


async def _prefetch_check(config: Any) -> list:
    """预下载检查：交给管理器按项目更新模式和凭据发现可下载的发行包。"""

    from .manager import M9AManager

    return await M9AManager.check_prefetch(config)


__all__ = ["M9AExpander", "active_runs"]
