#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""M9A 专项插件入口：用 MFW 积木跑《重返未来：1999》的 M9A 项目。

M9A 托管由 ``manager.M9AManager``（脚本级）与 ``account_run.M9AAccountRun``（账号级）运行，配置一律经
``config_view`` 读写；保存账号前的受管任务整理在 ``config_hooks``。登录、游戏更新、首任务时限、重试剔除
这些 M9A 自己的规矩是流程里的普通代码：规则常量与判据在 ``rules.py``、排队列与保存前整理在
``arrange.py``、登录的两种结局在 ``startup.py``；``login.py``（B 服登录）与 ``game_update.py``（官服客户端
版本检查与安装）由流程按需导入。插件声明在 ``plugin.py``，L3 外壳在 ``expander.py``。

照 SRC 专项在导入期导出 ``PLUGIN``：插件加载器只在执行本模块期间把导入错误（含「宿主仍内置 M9A」）
翻译成预检错误。流程模块（``manager``、``account_run``）只在函数里首次导入。
"""

from auto_mas_core import PLUGIN_API_VERSION

from .plugin import Plugin as PLUGIN

__all__ = ["PLUGIN", "PLUGIN_API_VERSION"]
