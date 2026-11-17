# 本仓库的维护范围

本仓库管理 ecommerce-image-workflow 技能源文件。修改技能、分析反馈、整理文档不表示授权生成商品图片。

- 完整制作规则以 references/workflow.md 为唯一正文；SKILL.md保留入口与必要不变量，修改时核对一致性。
- bundled/是保留许可证的第三方副本。不要静默修改、删除其许可或替换成未知版本。
- 不提交商品照片、参考图库、项目执行索引、生成图片、密钥或个人路径；第三方自带示例资源不属于用户项目素材。
- scripts/是供技能运行使用的工具；tools/是仓库验证和发布工具。dist/只放构建产物，不纳入Git。
- 改动文件工具后运行 python tools/verify_package.py；发布运行 python tools/verify_package.py --build。环境已具备Python和Pillow时不重复安装。
- 发布时按 [RELEASE.md](RELEASE.md) 执行，同步VERSION和CHANGELOG.md，README版本信息保持一致。未经用户明确要求“发布新版本”不自动上传GitHub、创建标签或Release；日常推送不升版本。
- 如需安装到宿主技能目录，从本仓库同步。不要将安装副本、旧流程快照与本仓库并行维护为多个源头。
- 日常修改和提交远程不自动同步本地安装副本；用户明确要求更新技能或同步安装副本时再执行同步。
