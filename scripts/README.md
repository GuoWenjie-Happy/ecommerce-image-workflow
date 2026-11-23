# 电商流程文件工具

固定入口：`ecom_files.py`。依赖 Python 3 与 Pillow；先检查现有运行环境，已有依赖不要重复安装。缺依赖时使用 `python -m pip install -r requirements.txt`。

`ecom_files.py` 的图片及检测报告输出拒绝覆盖既有文件；修改版本需新文件名。输入图片不会改写。脚本不生图、不抠图、不改标签、不换瓶、不修复背景，不给出视觉通过结论。项目记账另使用下述 `project_files.py`，明确允许的记录更新由锁和原子写入保护。

```powershell
# 查看实际尺寸、比例、透明通道、近白边缘采样与近似主体占比
python ecom_files.py inspect "产品素材目录" --report "工作目录\素材检查.json"

# 主图正方形等比导出1000宽；非方图拒绝拉伸或裁切
python ecom_files.py export "原件.png" "交付\主图\01.png" --width 1000 --square

# 详情保留实际比例，等比导出900宽；上采样会标明
python ecom_files.py export "详情原件.png" "交付\详情\01.png" --width 900

# 仅从通过项目录制作两类预览；输出放在图片目录之外
python ecom_files.py preview main "交付\主图" "交付\主图预览.jpg" --width 400 --columns 3
python ecom_files.py preview detail "交付\详情" "交付\详情图预览.jpg" --width 400

# 参考与交付文件均用相同编号作文件名，如01.png、02.jpg
python ecom_files.py count "参考\详情" "交付\详情" --report "工作目录\数量核对.json"

# 主图品牌框套版：内容图 + 项目模板PNG → 输出；有卖点槽时附slots与texts
python ecom_files.py composite-frame "生成原件\主图\01.png" "模板\主图品牌框.png" "工作文件\产品A\生成原件\主图\01_套框.png"
python ecom_files.py composite-frame "生成原件\主图\01.png" "模板\主图品牌框.png" "工作文件\产品A\生成原件\主图\01_套框.png" --slots "模板\主图品牌框.slots.json" --texts "工作文件\产品A\_临时\主图01_框文案.json"
```

`composite-frame` 只叠框、填槽与可选 `separators`，按槽 `font_size`/`font_scale` 出字，不改产品像素；模板与卖点放置规则见 [品牌框模板约定](../references/brand-frame-template.md)。

```powershell
# 模板壳/示意内容指纹（复用比对）
python ecom_files.py fingerprint "模板\头图品牌框.png"

# 壳内容区真透明硬检（不过不得当正式壳；可选 --min-clear，默认 0.80）
python ecom_files.py validate-shell "模板\头图品牌框.png" --safe-area 0.12,0.16,0.02,0.02

# slots 结构校验（可选对照壳尺寸）；满长看图自检仍须人工
python ecom_files.py validate-slots "模板\_模板缓存\头图品牌框.slots.json" --shell "模板\头图品牌框.png"
```

`validate-shell` 通过才可把壳写入跨项目 `_模板缓存`；失败登记 `shell_alpha: missing`。应急挖洞仅项目内 `derived_shell`，不得冒充正式壳。

详情预览按数字文件名顺序等宽、从上到下拼接，不拉伸或裁切。主图联系表保留完整图片。极长JPEG不支持时脚本报错，可以明确使用PNG或降低预览宽度，不能假称生成成功。

主体占比是背景阈值或alpha边框的近似测量，可能包含阴影，须人工核对；不应用其修正产品轮廓。检查白底时仅报告结果，不能据此宣称完整背景都为纯白。数量核对不检查文案或SKU，仍需审核。

每轮复用本脚本，命令参数指定本轮独立目录；不要复制到每个产品后各自改写。确有缺失功能时在本目录维护通用功能，不编写替代视觉制作的临时脚本。

## 项目文件批处理

固定入口为 `project_files.py`，只接收清单文件路径，不把整份JSON或提示词拼进命令行：

```powershell
python project_files.py "项目目录\工作文件\操作清单.json"
```

执行者用文件写入工具准备清单（不使用超长PowerShell命令），示例结构如下。`project_root` 在执行时填实际项目绝对路径，以下占位符不可直接运行。

```json
{
  "project_root": "<项目绝对路径>",
  "operations": [
    {"op": "environment", "target": "工作文件/环境.json"},
    {"op": "archive", "source": "<工具返回的原件绝对路径>", "target": "工作文件/产品A/生成原件/主图/01.png"},
    {"op": "json", "source": "工作文件/产品A/待写入记录.json", "target": "工作文件/产品A/product.json"},
    {"op": "timing", "target": "工作文件/产品A/product.json", "stage": "审核-第1轮", "action": "start"}
  ]
}
```

| 操作 | 行为与限制 |
|---|---|
| `environment` | 记录当前解释器、Pillow版本及检查时间；不扫描磁盘、不安装、不代表图片工具已可用 |
| `archive` | 原样复制并校验SHA-256；源可为明确的外部绝对路径，目标只在项目内且永不覆盖；不改名源文件或修改图片像素 |
| `json` | 从 `source` 文件或清单的 `data` 对象写入；默认拒绝覆盖。明确更新记录时使用 `replace: true`；推荐同时传读取时的 `expected_sha256`，过期就拒绝写入 |
| `json`＋`mode: merge` | 字典递归合并，其他值（包括数组）整体替换，不自动追加历史；补丁必须只包含本次授权变更，防止无意清空额度或记录 |
| `timing` | `action: start/finish` 记录UTC开始、结束及真实经过秒数；每次使用唯一阶段/尝试ID，不覆盖已记录回合，未finish不伪记完成 |
| `overview` | 读取 `project` 指定的项目索引，写 `target` 总览；后续更新需 `replace: true`。只核对明确计划、状态、选版来源和文件，不执行视觉判断 |
| `export` | `source`原件等比导出到`target`，需`width`和`approved: true`；主图加`square: true`；每项分别指定尺寸，返回原生/导出尺寸与上采样标记。即使`replace: true`也不覆盖图片 |
| `preview` | 根据明确的`files`列表生成`target`预览，需`kind: main/detail`及`approved: true`；可设width/columns，按数字编号排序。不扫描同目录其他旧图，不覆盖既有预览 |
| `inspect` | 明确的非空`files`列表批量检查，JSON写入`target`；不判视觉合格，不能拿空列表当检查成功 |
| `count` | 对比`references`与`files`两份明确图片列表的编号，JSON写入`target`；参考不可为空，交付列表可为空并报告全部缺号 |
| `inventory` | 扫描明确指定的source产品输入目录，将图片指标/哈希、文档路径、坏图和相同内容提示写入target；不识别事实、不分SKU、不删除重复照片 |
| `prompt` | 将source UTF-8文本中的最终提示词原文及tool、parameters保存到target Markdown，返回原文哈希；拒绝覆盖，不调用图片工具 |
| `compose` | 从source规格或执行卡指定job，检查六类identity、证据和附图角色，组装固定保真条款及逐图设计到target；拒绝覆盖，原文及输入变化由读取入口拒绝 |

每项完成后向终端输出一行带操作序号、目标路径及哈希的结果；遇错返回非零，后续项不执行。批次不是整体事务：已成功项保留，恢复时读取结果，只补跑失败和未执行项，不能盲目重跑整批。每个目标加独占锁、临时写入后原子替换；多产品仍各写各自索引，总控统一更新公共文件。遗留锁必须核实没有执行中的写入后处理，不自动删锁。

批次清单和待写入文件放 `工作文件/_临时/`，复用当前工作文件名，不为每次操作留多份重复JSON。实际生图提示词仍按流程逐图保存；该工具不调用任何图片API、没有生成或审核权限。文件归档树见制作规范第11节，工具仍按传入路径执行，不自动推断正确分类；执行者须使用规定目标路径并在收尾核对。

### 自动总览的数据要求

每产品 `product.json` 增加 `plan`，如 `{"main":["01","02"],"detail":null}`：列表是明确应交付编号，`null`是该类别不在范围；字段缺失写待核实，不能从已有交付数量推断计划。项目索引仍用 `products[].index` 引用产品记录。

`images` 按 `main/01`、`detail/02` 索引，只有 `status: passed`、`selected`明确、`delivered_from`等于该选版、`delivered`文件存在且可读，才计为当前已交付。导出成功后由执行者登记 `delivered_from`，不能在导出前预填成功。旧项目不自动猜选版来源，须先核对。

`project_files.py` 在 `json` 或 `timing` 写回同时含 `plan` 和 `images` 的完整产品索引前执行状态闸门。通过图的 `review` 必须含非空 `product`、`copy`、`composition`、`completeness`、`cross_page` 和 `conclusion: passed`；单句总评不通过。`repair_attempts` 须等于 `repairs` 条数，每条返修须关联实际 `image`、`prompt_file` 和结构化 `review`。`selected` 只能指向原版或已通过返修版；交付时 `delivered_from` 必须等于 `selected`。旧索引仍可读取和生成总览；下次写回前须先补齐新契约。

自动总览生成主图、详情数量和逐项异常；素材使用 `white_status/transparent_status` 及对应review登记。预览、素材模糊通过及上传限制仍须依事实补充总览；脚本成功不代表这些人工核验项已经完成。

### 一次调用批量交付

将所有已通过图片逐项列入同一份operations：先export，再inspect、preview和count，最后更新产品索引及overview；一次调用即可按依赖顺序完成，不需要AI每导出一张重新发命令。所有图片输出使用新文件名/独立版本目录，确认选版后更新索引；不通过覆盖旧图来实现交付更新。

以下是operations片段示例，放入上方含project_root的清单。`approved: true`是执行者已完成审核并选版的声明，脚本不会自行授予通过状态。源文件允许明确的外部绝对路径；所有target只能在指定项目内。

```json
[
  {"op":"export","source":"工作文件/产品A/生成原件/主图/01.png","target":"交付/产品A/主图/01.png","width":1000,"square":true,"approved":true},
  {"op":"export","source":"工作文件/产品A/生成原件/详情/01.png","target":"交付/产品A/详情/01.png","width":900,"approved":true},
  {"op":"inspect","files":["交付/产品A/主图/01.png","交付/产品A/详情/01.png"],"target":"工作文件/产品A/导出检查.json"},
  {"op":"preview","kind":"main","files":["交付/产品A/主图/01.png"],"target":"交付/产品A/主图预览.jpg","approved":true},
  {"op":"preview","kind":"detail","files":["交付/产品A/详情/01.png"],"target":"交付/产品A/详情图预览.jpg","approved":true}
]
```

这类批次内部仍逐项顺序处理；收益是减少AI编排和工具往返，并非同时并行缩放。每项结果单独返回目标、哈希及尺寸等指标，失败返回序号和目标，后续项不执行。核对结果后只恢复未完成项；不能因一项成功就把所有导出记为成功，也不能在导出之前更新对应交付状态。检测报告可汇入产品索引后复用当前工作文件，不按每张图片拆额外JSON。

透明底审查preview可设 `background: "#202020"` 或白色，按需生成浅深背景联系表，不修改输入alpha或商品像素。此时approved表示允许纳入审查预览，不等于视觉通过；交付预览只能包含通过项。

inventory排除.git、_参考缓存和__pycache__；errors非空时必须核对披露。prompt只证明已留存，执行者必须将同一原文实际传给图片工具，并根据真实调用更新索引；不要在parameters中放任何认证信息。

新增生图及返修使用compose，随后 `python prompt_builder.py "组装记录.md"` 输出校验后的完整请求供宿主工具直接使用；不另写或缩减提示词。prompt保留为实际外来/历史调用留存入口，不绕过新任务必填检查。字段、参数与限制见 [产品保真组装](../references/prompt-builder.md)。

## 参考图批量缓存

传给工具的临时清单与payload统一位于本轮 `工作文件/_临时/`，不放商品或参考库根目录。脚本不自行删除输入；执行者核对成功、记录归并且无引用后按制作规范第11节清理，失败待恢复时保留。单独前置任务可使用该任务自己的临时工作区，永久缓存位置不变。

临时目录写入时才创建，收尾不为检查创建目录；最后确认本轮临时目录为空且无任务依赖，再以非递归空目录删除操作移除。不能用递归删除代替空目录检查。

入口：`python reference_cache.py "参考准备清单.json"`。一次可列多套确有比较需要的参考，不默认处理整个图库。root填真实套系绝对路径，目录名按实际填写：

```json
{"sets":[{"root":"<套系绝对路径>","categories":{"main":"主图","detail":"详情图"},"analysis_rules_version":"1"}]}
```

只做详情仅传detail。直接读取类别目录内图片，不递归误收缓存。默认写该套系 `_参考缓存/`；未授权写参考库或只读时，清单显式填cache为项目 `公共参考/<套系ID>/` 的绝对路径，不自动寻找或切换位置。不同来源不得共用cache。

正常清单省略cache，使用默认路径。非默认cache必须同时提供cache_override对象：kind为write_error、permission_restriction或user_request，evidence填写实际写入错误、明确限制写入范围的规则或用户指定位置的原话；不因用户填写了项目输出目录就推断参考库未授权。脚本检查声明结构并将原因登记到缓存索引和返回结果，不验证声明真实性，执行者必须核实并告知用户。缺原因时拒绝创建备用缓存，不能改用临时脚本绕过。

稳定输出为index.json、main_overview.jpg和detail_overview.jpg。索引记录路径、编号、排序、宽高、比例、内容哈希、fingerprint、总览路径及哈希；未变化复用，新增/删除/改名/替换仅更新受影响类别，总览损坏重建。空目录、坏图报错，不生成空尺寸报告；重复内容不去重，重复编号用duplicate_ids提示，必须核对后建立映射。

缓存index使用schema_version=2：source_base=cache_directory，默认source=".."；categories.files.path相对套系、preview相对缓存目录。cache_location.path_base=suite，default与actual相对套系；仅跨盘符外置路径无法相对化时source_external/actual_external=true。临时清单和命令返回的source/cache仍可为当前绝对路径，不应据此手工覆盖持久索引。v1来源与当前套系不同的缓存，仅在清单指纹有效、全部已记录原图按相对路径存在且SHA-256一致时自动迁移，保留AI分析原文及指纹；不一致则报错且不覆盖旧索引，需核对映射，不自动猜另一套参考。

工具不分析设计。AI完成原参考分析后另写main_analysis.json/detail_analysis.json，包含source_fingerprint（当前fingerprint）、rules_version（当前analysis_rules_version）及非空analysis。指纹或规则不匹配时analysis_required为true；规则变化只需重分析，不无故重拼总览。公共分析不代替每产品专属风格配色与文案。

每类返回changes，逐张列added、removed、modified、unchanged（原图相对路径），sequence_changed说明文件顺序清单有变；改名按删除加新增处理。changes对比上次扫描，analysis_changes对比有效AI分析所依据的原图，分析未完成时重复扫描不会清空待办。analysis_scope为none时复用，为incremental时只处理变化图片及受影响结论；为full时表示首次分析、规则改变或有效分析依据缺失，需重新建立该类基础分析。仅总览损坏不会触发原图重分析。

缓存加锁，索引原子写入，原参考不修改，未登记的同名总览不覆盖。总控统一准备、产品任务只读共享，避免并行重复制作。全流程分工见 [批量检查表](../references/batch-operations.md)。

## 前置参考分析与公共选套索引

AI分析文件仍使用source_fingerprint、rules_version、analysis。新分析的analysis结构如下（逐图字段填写具体观察，不照抄示例）：

```json
{"pages":[{"path":"主图/01.jpg","sha256":"<当前原图哈希>","order":1,"content":"原图具体标题、辅助文字、信息组和图像内容","purchase_task":"页面购买任务","expression":"表达力度及依据","image_text_relation":"图文位置、对应及支撑关系","composition":"主体、区域、层级、遮挡","transfer":"可迁移机制与不可照搬事实","uncertainties":"不确定内容；没有则明确写无"}],"suite_style":"整套字体、配色、光影和装饰关系","selection":{"product_forms":"形态适配","design_features":"设计特点","modules":"模块组成","required_materials":"所需素材","adjustable_items":"可调整项"},"review":{"status":"passed","checked_paths":["主图/01.jpg"]}}
```

每个类别pages按扫描files顺序覆盖全部原图，order从1开始；路径和哈希须准确绑定。review记录AI实际对照原图抽查的路径，不能填脚本通过代替看图。旧分析可以保留，结构不足时公共索引标incomplete，补全后才作为详细分析复用。

批量入口：`python reference_catalog.py "参考库清单.json"`，清单示例：

```json
{"root":"<参考库绝对路径>","sets":[{"suite":"水果/套系01","categories":{"main":"主图","detail":"详情图"},"analysis_rules_version":"1"}]}
```

全库前置（含完整制作中的前置）的sets列出枚举到的全部套系；定向操作可仅列候选但不能声称覆盖全库。工具逐套复用reference_cache检查文件，再将有效分析汇总为根目录_公共参考中的选套索引.json及选套说明.md；不调用AI、不自动生成或修改分析。运行可先产出missing列表，AI批量完成所需分析后再汇总。类别状态ready/missing/stale/incomplete全部保留；出错停止、返回失败，不能把旧索引当本次成功结果。索引JSON为机器读取依据，说明文件仅供浏览；详细内容仍读取套系分析，哈希匹配不证明AI观察准确。

公共索引v2的source="."、path_base=reference_library；suite、cache、categories.*.analysis_file均相对当前参考库根目录，统一用/分隔。例：cache="水果/套系01/_参考缓存"，analysis_file="水果/套系01/_参考缓存/main_analysis.json"。读取时以_公共参考上一级为根，不以进程cwd为根。若cache_external/analysis_file_external=true，须按标记解析外部路径并披露不可单独搬库；其余相对路径也可能指向库外缓存，迁移时须同时保持相对关系。build不沿用旧公共索引的绝对地址，始终从清单指定的当前根与缓存重建v2公共索引。仅检查不更新时不要运行build/prepare，它们会写缓存；只读核验后在授权更新时迁移。

## 项目与模板索引路径迁移

入口：`python index_paths.py "路径迁移清单.json"`。这是定向字段迁移，不自动发现或重写所有JSON，不生成/复制图片。执行者先枚举实际引用字段、确认文件基准和外部依赖，再填写清单；不要把业务文案、历史调用或检测报告当资源索引字段选入。

```json
{"apply":false,"mappings":[{"from":"<旧项目绝对根>","to":"<当前项目绝对根>"}],"documents":[{"base":"<当前项目绝对根>","file":"project.json","fields":[{"pointer":"/products/0/index"},{"pointer":"/inputs/products"}]}]}
```

默认apply=false只检查、返回拟修改内容，授权后改true再运行。base为当前索引的资源基准，file相对base且必须为现有JSON；项目/产品/执行卡统一用项目根，模板用模板根。fields只处理列出的JSON Pointer（数组用数字，键中的/写~1、~写~0）；旧相对路径如不以当前base为准，可在该field写from_base为明确旧绝对基准，再通过mappings定位。映射按完整目录边界、最长匹配解析，支持Windows及POSIX旧路径，不进行字符串全局替换。产品selected、delivered_from等同义引用须一起列出，不能只迁一处；新schema标记及索引语义仍由执行者按流程核对维护。

全部文档先预检再写；内部结果统一相对base，越界依赖只有field显式external=true才允许保留为当前绝对外部路径，并返回external状态。目标必须存在；field指向带sha256的path/file时校验证据，不绕过其他业务状态或语义校验。模板应列shell/path、example/path、cache、slots、report等实际字段；执行卡应列source_images及逐job.references等；可选字段不存在不要写入清单。每份JSON写前加锁并核对旧哈希、原子替换；写入阶段失败可能已有部分成功，按实际文件恢复，不承诺跨文件事务回滚。工具不修改Markdown快照、不改状态、不删除旧文件；真实迁移完后须复查索引引用关系及可读性。

历史提示词不使用本工具改写，改用prompt_builder.py的--project-root和--path-map仅在读取时映射、逐图校验指纹，详见产品保真组装说明。环境记录的旧解释器路径应在换机后重新检查，不简单替换为当前机器路径。
