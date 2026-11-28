#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025-2026 AUTO-MAS Team
#   SPDX-License-Identifier: AGPL-3.0-or-later

"""M9A 调三块服务插件（运行、agent 环境、项目 / 项目更新）的入口。

:data:`SLOT` 是本包模块级的服务槽：插件 ``on_enable`` 绑宿主给的解析器、``on_disable`` 解；管理器、
账号流程、外壳手里没有插件实例，经 :func:`client` 从槽里现取服务。:data:`REQUIRES` 是插件的
``requires``（三个专项共有的操作，加项目更新状态查询和外壳导入所需的操作）。

本模块只导入专项共用库，不导入三块服务插件（规则 L）。
"""

from maafw_adapter_kit.services import (
    ADAPTER_REQUIRES,
    PROJECT_MANAGED_FIND,
    PROJECT_PEEK_OPS,
    SHELL_IMPORT_OPS,
    ServiceClient,
    ServiceSlot,
)

PLUGIN_ID = "m9a_adapter"

#: 本插件的服务槽（插件启用时绑、停用时解）。
SLOT = ServiceSlot(PLUGIN_ID)

REQUIRES = (
    *ADAPTER_REQUIRES,
    *PROJECT_PEEK_OPS,
    *(operation for operation in SHELL_IMPORT_OPS if operation != PROJECT_MANAGED_FIND),
)


def client(caller: str = "") -> ServiceClient:
    """经 :data:`SLOT` 调服务的客户端（每次调用都现取服务）；``caller`` 只进后端 debug 日志。"""

    return ServiceClient(SLOT, caller=caller)


__all__ = ["PLUGIN_ID", "REQUIRES", "SLOT", "client"]
