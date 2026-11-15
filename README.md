# 电商图片制作 skill · 1.0.0

支持完整制作或单独阶段；按产品名和图片编号定位文件。分发包不含作者商品、参考图库、密钥或测试图片。

## 安装

解压后将整个 `ecommerce-image-workflow` 文件夹放入宿主的技能目录。Codex通常为 `~/.codex/skills/`；遵循使用者实际环境的技能发现机制。不要把文件夹内文件逐个拆散。无需仓库规则。

包内包含流程、模板、文件脚本和两个MIT依赖。完整制作还需安装 `amazon-white-background` 和 `detail-flow`，来源及能力要求见 `references/dependencies.md`。本ZIP不是四个依赖全部预装的离线包，不会自动下载缺失技能。

文件工具依赖Python3和Pillow：已有依赖直接复用，缺少时对所选解释器执行 `python -m pip install -r <本技能目录>/scripts/requirements.txt`。技能本身不提供生图账号或服务。

## 使用

```text
使用 $ecommerce-image-workflow，完整制作。
商品目录：…
范围：全部产品
参考库：…
项目输出目录：…
```

已有项目提供总目录即可：`使用 $ecommerce-image-workflow，项目总目录：…，仅返修山茶油主图03，要求：…`。也支持素材处理、参考分析、文案策划、仅审核、图片制作、导出交付。阶段输入不足会列明缺项，不自动扩成整套。

首次生成项目索引后，后续按商品名和编号定位。新对话或换电脑无法定位项目名称时，只需提供项目总文件夹一次。分享项目需同时分享必要输入，索引不会让缺失图片自动出现。

## 维护

本仓库根目录即技能根目录，移动时连同隐藏文件和 `.git`（初始化后）整体移动。商品与制作项目留在仓库外。

### 验证与打包

在仓库根目录运行（用实际可运行的Python解释器替换 `python`）：

```text
python tools/verify_package.py
python tools/verify_package.py --build
```

第一条验证元数据、包内引用和文件工具；第二条验证后生成 `dist/ecommerce-image-workflow-<VERSION>.zip`。压缩包固定包含一层技能文件夹，按允许清单打包，不带Git、开发工具、项目数据或历史ZIP。版本由 `VERSION` 管理，变化记入 `CHANGELOG.md`。上传GitHub时提交源文件，ZIP通过Release附件分发。

验证脚本不代替真实生图测试，也不包含官方skill校验器。本地首版尝试官方校验时缺少PyYAML且网络不可用，未宣称官方校验通过。

安装后的 `references/workflow.md` 是完整规则正文；`SKILL.md` 是入口；`references/prompts.md` 是模板；`scripts/` 是文件工具。发布源在这个技能文件夹，后续改动以此为准，不再与外部流程文档同时维护两套。更新后重新打包，接收者替换自己的技能目录；项目文件保留在安装目录外。

第三方原文件和许可证保存在bundled，不混入本技能的自主维护正文；详细来源见 `references/dependencies.md`。本版只做本地结构及文件工具检查，尚未用封装入口进行真实生图回归，不能将其描述为已验证整套成图效果。
