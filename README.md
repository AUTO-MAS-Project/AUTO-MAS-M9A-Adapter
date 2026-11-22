<!-- auto-mas:i18n
{"display_name_i18n":{"zh_CN":"M9A 专项","en":"M9A Adapter","ja":"M9A アダプター"},"description_i18n":{"zh_CN":"用 M9A 跑《重返未来：1999》日常。","en":"Run Reverse: 1999 daily tasks with M9A.","ja":"M9A で『リバース：1999』のデイリーを実行します。"},"tags_i18n":{"zh_CN":["重返未来：1999","脚本适配"],"en":["Reverse: 1999","Script adapter"],"ja":["リバース：1999","スクリプト"]}}
-->

# AUTO-MAS M9A Adapter

从 AUTO-MAS 插件中心安装并启用 M9A 专项。新建托管时导入 M9A 项目目录，在账号页编辑任务队列。启动游戏、切换账号、关闭游戏这三项由 MAS 按固定顺序补进队列；B 服可以选「由 MAS 登录」。

本插件依赖 MFW 的三块服务插件（agent 环境、运行、项目更新）和两个库（interface 解析、原生库识别），启用时会先启用上游插件。0.1.0 是联调版本：执行入口沿用原来的脚本级管理器，跨插件调用大多仍是直接导入，已知问题见拆分契约文档。

配套宿主需要不再内置 MFW、M9A、MSS（让位分支）；仍内置时加载本插件会报错并提示换分支。由内置 M9A 升级的托管继续使用已有账号：旧配置里的 `UserData` 在加载时改名为 `users`，UID 与顺序不变。

开发时把本仓库目录联接到配套宿主的 `plugins/m9a_adapter`，通过插件中心加载。测试时设置 `AUTO_MAS_HOST_SOURCE` 指向宿主检出目录，用宿主的 Python 3.12 环境运行 `python -m pytest tests`。

发布由 AUTO-MAS-Project 的 `publish.yml` 使用 `pypi` 环境与同组织的 PyPI Trusted Publisher 完成。只有匹配包版本的发布标签会上传分发包。
