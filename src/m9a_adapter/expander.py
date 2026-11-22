#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""M9A 的 L3 外壳：0.1.0 把整轮交给沿用的脚本级管理器 ``manager.M9AManager``。

插件路径在建 L3 之前，L2 已经拿了托管的 X 锁（``cascade=False``）；旧路径在 L2 给管理器的几样东西
（``history``、``context``、``maintenance``、「管理器自己展开账号」标记）在这里补上，管理器以
「宿主已持锁」模式运行，不再自己拿锁。L3 自己的账号循环、``build_worker`` 都不用。
"""

from __future__ import annotations

from typing import Any

from auto_mas_core import TaskMode, UserExpander


class M9AExpander(UserExpander):
    """0.1.0：整轮交给沿用的脚本级管理器；L3 只做外壳。"""

    async def main_task(self) -> None:
        await self.script_info.set_state(status="运行")
        self._entered = True
        from .manager import M9AManager  # 规则 L：函数内导入

        manager = M9AManager(self.script_info, host_locked_config=self.script_config)
        manager.history = self.history
        manager.context = self.context
        manager.maintenance = False
        # L2 收尾时复位（app/task/script_expander.py:344）
        self.script_info._manager_controls_users = True
        try:
            await manager._execute_task()
            error = manager.execution.error
            if error is not None and type(error).__name__ == "FluxdownCancelUnconfirmed":
                raise error
        finally:
            await manager.callbacks.close()
            if self.task_info.mode == TaskMode.AUTO_PROXY:
                manager.finalize_completion_details(self.script_info)

    def build_worker(self, user: Any, config: Any) -> Any:
        raise NotImplementedError("0.1.0 由 main_task 整轮交给管理器")


async def _prefetch_check(config: Any) -> list:
    """预下载检查：交给管理器按项目更新模式和凭据发现可下载的发行包。"""

    from .manager import M9AManager

    return await M9AManager.check_prefetch(config)


__all__ = ["M9AExpander"]
