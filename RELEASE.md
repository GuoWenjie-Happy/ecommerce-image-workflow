# 发布流程

本仓库区分日常更新和正式发布。日常更新持续进入 `main`，正式发布才建立版本号、Git 标签和 GitHub Release。除非用户明确要求“发布新版本”，否则不执行正式发布。

## 用户指令

- “更新并推送”：完成修改、验证、记录未发布变更、提交并推送 `main`。
- “发布新版本”：执行本文的完整正式发布流程。

## 日常更新

日常更新不修改 `VERSION`，不创建 Git 标签或 GitHub Release。

1. 在 `CHANGELOG.md` 的“未发布”下记录本次用户可感知的变化。
2. 按改动范围运行测试；修改技能、文档或文件工具后运行：

   ```text
   python tools/verify_package.py
   ```

3. 核对 `git diff`，只提交本次相关文件。
4. 提交并推送当前 `main`：

   ```text
   git push origin main
   ```

推送完成不代表产生了新版本；“未发布”内容继续累计，直到用户明确要求正式发布。

## 版本号选择

版本号遵循 `主版本.次版本.修订号`：

- 修订号（例如 `1.0.0` → `1.0.1`）：修复错误或澄清规则，不增加不兼容行为。
- 次版本（例如 `1.0.0` → `1.1.0`）：增加向后兼容的能力或明显扩展流程。
- 主版本（例如 `1.0.0` → `2.0.0`）：存在不兼容的入口、目录、数据契约或流程变化。

版本必须高于已发布版本。同一版本号只能发布一次；已推送的标签不得移动或覆盖。

## 正式发布

1. 确认当前位于 `main`、工作区只包含本次发布内容，并读取“未发布”决定版本级别。
2. 将新版本写入 `VERSION`。
3. 保留 `CHANGELOG.md` 顶部空的“未发布”，把现有条目移动到 `## X.Y.Z · YYYY-MM-DD`。
4. 核对 README 中的版本信息和发布入口与新版本一致。
5. 运行完整验证并构建 ZIP：

   ```text
   python tools/verify_package.py --build
   ```

6. 确认生成 `dist/ecommerce-image-workflow-X.Y.Z.zip`，并检查验证命令无失败。
7. 提交发布元数据和源文件，然后先推送 `main`：

   ```text
   git push origin main
   ```

8. 为同一个发布提交创建并推送带说明的标签：

   ```text
   git tag -a vX.Y.Z -m "Release X.Y.Z"
   git push origin vX.Y.Z
   ```

9. 在 GitHub 以 `vX.Y.Z` 标签创建 Release，发布说明使用对应的 CHANGELOG 条目，并上传 `dist/ecommerce-image-workflow-X.Y.Z.zip`。
10. 检查 GitHub 上的 `main` 提交、标签、Release 版本和 ZIP 文件名四者一致。

`dist/` 是本地构建产物，不提交到 Git；ZIP 只作为 GitHub Release 附件分发。

## 发布失败时

- 验证或构建失败：停止，不提交版本、不打标签；修复后重新运行完整验证。
- `main` 已推送但标签尚未推送：修复发布提交并重新验证，再创建标签。
- 标签已推送但 GitHub Release 尚未创建：不得移动标签；使用该标签继续完成 Release。
- 已发布的源码或 ZIP 有实质错误：不得覆盖原标签或附件来伪装同一次发布；修复后发布新的修订版本。
