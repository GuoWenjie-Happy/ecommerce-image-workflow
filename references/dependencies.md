# 依赖与可分发边界

## 包内与外部依赖

### 内置技能来源与更新定位

以下路径相对本技能根目录；poster-style-transfer与文案技能的上游入口位于其仓库根目录，图片技能集合的各入口位于 `skills/<技能名>/SKILL.md`。来源地址于2026-11-15核对，不代表所有包内副本已更新到上游最新版本。

| 内置技能 | 上游来源 | 本仓库副本入口 | 版本可追溯情况 |
|---|---|---|---|
| poster-style-transfer | [jiemianduan/poster-style-transfer](https://github.com/jiemianduan/poster-style-transfer) | [bundled/poster-style-transfer/SKILL.md](../bundled/poster-style-transfer/SKILL.md) | 包内元数据标注0.1.0；导入时上游提交号未记录 |
| ecommerce-visual-copywriting | [feichanggege/ecommerce-visual-copywriting-skill](https://github.com/feichanggege/ecommerce-visual-copywriting-skill) | [bundled/ecommerce-visual-copywriting/SKILL.md](../bundled/ecommerce-visual-copywriting/SKILL.md) | 当前包内入口无明确版本号，导入时上游提交号未记录；不能根据外部安装副本或上游当前版本推定本副本版本 |
| ecommerce-image-skills（含amazon-white-background） | [xianyu110/ecommerce-image-skills](https://github.com/xianyu110/ecommerce-image-skills) | [白底技能入口](../bundled/ecommerce-image-skills/skills/amazon-white-background/SKILL.md) | 2026-11-15导入提交 `f4566fdc812584425728862ad8e08c90883d81ee`，完整保留53个上游跟踪文件，不含.git元数据 |

三份依赖的MIT许可证均保留在各自包内根目录的 `LICENSE`。图片技能集合的来源、提交及逐文件SHA-256清单另见 [导入清单](ecommerce-image-skills-source.json)，更新该集合时同步维护清单。来源登记与本流程的集成说明维护在本文件，不为了加来源而改写第三方原文件。

用户说“更新内置 poster-style-transfer”或“更新内置 ecommerce-visual-copywriting”时，按此表定位上游和本仓库的 `bundled/` 副本。先读取上游规则及许可证，比较包内差异和所需附属资源，保留许可证与版权声明；不能拿宿主另一份同名技能直接覆盖，也不直接对本仓库执行指向上游的 `git pull`。

用户说“更新内置 ecommerce-image-skills”或“更新内置白底技能”时，定位上表图片技能集合，按明确的上游提交检查和更新完整集合及导入清单；若只更新单个子技能，须明确记录分组件版本，不能继续把整个目录标成原提交的完整快照。

更新时明确目标tag或提交，检查与本流程的调用职责、参考文件、脚本和许可兼容后同步所需完整资源；版本字段（若有）、实际采用的上游提交号、更新日期、引入文件范围及必要差异说明登记在此并记入CHANGELOG。没有可靠导入提交记录时明确未知，不用“最新版”代替版本依据。更新后运行仓库验证；涉及制作行为时区分结构验证与真实成图回归，不为更新依赖擅自生图。

只更新本仓库副本不等于更新宿主已安装技能。安装同步按当前环境规则另行执行，不把个人安装路径写入可分发源文件。笼统的“更新电商技能”不能自动扩成更新全部第三方依赖；按用户明确指定的组件处理，范围不清时先核对差异再说明。

### 各依赖职责

- `../bundled/poster-style-transfer/SKILL.md`：原版MIT许可，随目录保留LICENSE及附属参考。优先使用此包内版本，运行直接生成、风格分析或定向迭代。
- `../bundled/ecommerce-visual-copywriting/SKILL.md`：原版MIT许可，保留LICENSE及运行参考、素材和脚本。用于商品证据、逐图文案及执行卡；内部自审留工作目录，不强加用户确认或长篇交付。
- `amazon-white-background`：素材阶段及完整制作直接读取包内 `../bundled/ecommerce-image-skills/skills/amazon-white-background/SKILL.md`，无需单独安装。许可证来自集合根目录MIT LICENSE，不再因子目录无独立LICENSE而误判未授权。完整集合含12个技能，仅按本流程职责调用白底；不启动ecommerce-listing-suite的整套策划或其他未请求阶段，不自动注册全部子技能到宿主。
- 白底技能附属脚本位于其入口旁 `scripts/`，集合共用脚本位于 `../bundled/ecommerce-image-skills/scripts/`。内置图片能力优先；本流程不执行上游收费API、推广链接及无限重试路线，也不使用检查脚本的 `--fix` 自动重裁或改像素。白底检查脚本依赖Pillow及NumPy，按需复用已安装环境；缺少时准确报告，不自动安装。其他文件检查继续使用本技能 `scripts/ecom_files.py`。
- 第三方技能中的相对脚本路径以被读取的第三方 `SKILL.md` 所在目录解析，不以项目当前目录或本总控根目录解析。白底检查使用 `<本技能根目录>/bundled/ecommerce-image-skills/skills/amazon-white-background/scripts/check_main_image.py <白底原件绝对路径> --json`，调用前展开真实绝对路径；读取JSON内各指标，不把命令退出成功等同于商品视觉验收。脚本的尺寸与背景阈值仅是辅助指标，本流程的产品保真、素材像素披露、构图与返修规则仍优先。
- `detail-flow`：外部必需（成图审查阶段及完整制作），来源：https://github.com/AJbeckliy/detail-flow-V2-Ajie 。仅借用审查模式，不执行其Starcanvas、HTML或安装后端链。本地未找到独立分发许可，因此未复制。

不要自动安装或覆盖其他技能、运行陌生下载脚本或购买服务。缺失依赖列出准确名称及上面来源，用户安装后复查继续；不谎称一个ZIP已包含全部第三方技能。用户提供分发许可后可另做完整依赖包。已知来源仅用于定位，不代表已在线验证最新版本。

## 环境检查按阶段执行

- 可读取项目和技能文件，写入指定输出目录；可看本地图片。
- 生成/返修：宿主有图片生成、带参考编辑能力；透明底阶段有真实alpha输出能力。不指定后台模型，不因依赖文档中模型名而转收费API。
- 文件工具：Python3与Pillow（`scripts/requirements.txt`）；先测已有解释器，不写死环境路径。
- 平台当前规则核验：网络搜索与官方页面读取。无法核验时标记未核验，不以旧值保证兼容；不影响其余已授权制作。
- 子代理为可选并发能力，缺失时隔离顺序执行；不是安装失败。

安装技能不等于自动获得生图服务、联网权限或宿主付费额度。仅文案/参考分析不要求安装白底依赖；导出已有通过图不要求生图能力。准确披露当前受阻阶段，并继续独立可做工作。
