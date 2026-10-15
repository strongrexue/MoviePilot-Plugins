"""EmbyCoverCenter 业务服务层。

后续里程碑在此目录补齐：
- mediaserver.py  媒体服务器发现（已就绪）
- emby_gateway.py 宿主媒体服务器模块透传（get_data / post_data）
- render_engine.py / layouts/ 封面渲染引擎与布局
- cover_task.py / cover_backup.py 自动封面任务与备份恢复
- emby_tasks.py   Emby 计划任务归一化与操作
- notify.py       通知组装（走宿主 post_message）
"""
