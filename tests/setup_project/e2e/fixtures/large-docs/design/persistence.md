# 持久化

写盘前对 JSON 做 `sort_keys=True` 序列化，保证同样内容产生同样文件，便于 git diff；备份文件后缀为 `.bak1` 到 `.bak3` 轮转。
