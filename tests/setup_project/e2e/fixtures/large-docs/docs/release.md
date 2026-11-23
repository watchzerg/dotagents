# 发布

打 tag `vX.Y.Z` 后 CI 构建 wheel；构建前检查 `pyproject.toml` 的版本号与 tag 一致，脚本为 `scripts/check_version.sh`。
