# 产品保真提示词组装

job.style来自当前执行卡的最终方案：选套后结合商品特点、文案主题与参考构图及色彩关系共同策划，在style_basis记录依据和配色理由，style再展开到各job，不提前锁死商品风格或直接复制参考配色。同参考多产品分别判断，不复制首个产品style，也不要求强制异色。页面特有装饰只写入适用job，视觉要求不得改写商品事实或省掉必要文案。组装器只校验和组装文本，不证明设计判断成立，决策规则见制作规范第4、7节。

本流程的新增白底、透明底、营销图与返修调用使用project_files.py的compose操作。AI填写商品观察及本张设计，不自行压缩成“只保留品牌、品名、容量”。

**默认生图串**：把六类观察收成短「商品核对」+ 一遍硬要求（学自观察表与保真条款，不逐条重复长文）；**不再**默认贴英文字段整表，也**不再**默认追加保真全文。商品不变主要靠 **product 附图 + 商品核对**。

**仓库归档（可改回）**：

- 完整六类观察表：仍写在执行卡 `identity`，规范见下表。  
- 保真条款原文：仍保留 [product-preservation.txt](product-preservation.txt)，勿删。  
- 测试若要恢复旧提示词形态：job/规格设 `"full_legacy_preservation_prompt": true`，compose 会再写入「整表观察 + 保真全文」（`prompt_mode: legacy_full`）。

## 商品观察表（执行卡必填；默认不整表进生图串）

在商品识别阶段，对照实际原图填写执行卡内的identity；白底、透明底、营销图和返修共用该产品/适用SKU的观察表。字段：

| 字段 | 必须观察的内容 |
|---|---|
| shape_proportions | 外形、长宽和各部分比例，不能只写品类名 |
| structure | 盖、孔、把手、接口、缝线、链节、镶嵌等适用结构及关系 |
| colors_materials | 各区域的可见颜色、纹理、表面和透明特性；材质事实有证据才写 |
| graphics_patterns | 标签形状、图案、印花、徽记及位置，不能只写Logo |
| text_regions | 全部可见文字区的数量、位置、主次排布；可读文字准确记录，不可读区说明可见纹理和模糊状态，不能省略成空白 |
| accessories | 可确认随货附件及位置；不能把拍摄道具当售卖附件 |

每字段包含status和description。status只允许observed、not_visible、not_applicable；后两者仍须在description写原因，不填猜测。脚本检查结构与非空，不证明AI已正确识别图片，也不能自动判断是否漏了某个标签区域；观察表和实际附图必须由AI复核。

identity还须有product_id和非空source_images（原商品证据图路径），脚本校验文件可读并记录哈希。独立测试可重新看原图填写，但固定条款和六类检查项不得弱化；这不强制复用上一轮所有成果，不改变完整重跑授权范围。

## 组装清单

执行卡可集中存 `identity` 和按main/01、detail/02等索引的 `jobs`，各job包含下列内容；也支持source直接指向单张完整规格对象。

```json
{
  "stage": "main",
  "product_visible": true,
  "output_spec": "1000×1000px，1:1",
  "references": [{"path":"<真实商品素材路径>","role":"product"},{"path":"<本张原参考路径>","role":"design"}],
  "style": "<本产品风格>",
  "layout": "<本张完整构图>",
  "copy": "<全部准确新增文案摘要；无字时明确写无新增文案>",
  "dense_copy": false,
  "copy_units": [
    {"id": "L1", "title": "<短标题>", "body": "<完整说明句>"},
    {"id": "R1", "title": "<短标题>", "body": "<完整说明句>"}
  ],
  "constraints": "<本张限制>",
  "parameters": {"transparent_background": false},
  "full_legacy_preservation_prompt": false
}
```

`dense_copy`：双列对照、多行表、四宫格及以上且每格有正文、参数表等密文页必须为 `true`，并提供非空 `copy_units`；每一项须有可上图的 `title` 与 `body`（仅短印章位可 `"title_only": true`）。缺说明时 compose **失败退出**，不得生图。非密文页可省略 `copy_units`；一旦提供则同样校验完整性。组装成功后写入「上图文字分位」与禁止自撰句。

`identity_check`：**按需**附图，不默认每张都带第三张。

### 生图前硬闸（compose 失败即停）

| 检查 | 失败行为 |
|---|---|
| `copy` / `copy_units` 含禁词（`资料来源`、`来源：`、URL、`文案溯源`、`产品保真`、`商品保真`、`执行备注`、`准确文案`、`copy_units` 元标记等） | compose 失败 |
| 已有 `copy_units` | 提示词**不**再写入整段摘要，只保留上图文字分位 |
| `uses_brand_frame: true` 但无 `safe_area` 且 layout 未写「安全区」 | 失败 |
| `physical_scale: true` 但未写 `scale_alignment` | 失败；默认不做实物对照 |
| 未开 `physical_scale` 但 `layout` 点名硬币/直尺/钢蹦 | 失败（分级默认纯表） |
| `icon_list: true` 但未声明 `icon_uniform: true` | 失败 |
| `page_kind` 为信任/证明类，且 design 附图路径含证书/SGS/章面/报告暗示 | 失败并提示换附图策略 |
| `multi_panel: true` 但缺合法 `panel_count`（≥2） | 失败 |

可选字段：`prop_whitelist`、`extra_chrome`、`panel_count`、`page_kind`。脚本只拦登记字段与禁词；提示词段位与白话展开由执行者按制作规范填写，不另开「提示词审核」阶段。成图对错仍看图验收。

stage允许white、transparent、main、detail、repair。出镜商品必须附product角色图；返修必须附edit_target当前编辑图。其他角色为design和identity_check。明确不出镜时仍要附参考，product_visible为false并填absence_reason，不能生成另一种包装凑版。素材阶段不允许不出镜。

各阶段references必须落实真实用途：白底用对应原照作product，透明底用已验收白底，营销图用匹配高清白底/透明底；source_images用于追溯商品原证据，不会自动全部附入模型。scripts只检查角色存在、路径可读，不能判断选错SKU、附图是不是已验收或角色是否写错。

在项目操作清单中逐图或批量添加：

```json
{"op":"compose","source":"工作文件/产品A/执行卡.json","job":"main/01","target":"工作文件/产品A/生图提示词/主图/01_初始.md"}
```

商品核对（或 legacy 下的观察表+保真全文）、尺寸及逐图设计被确定性组装；快照记录参数、来源与附图哈希，以及 policy/identity/prompt 哈希与 `prompt_mode`。参数中的prompt和referenced_image_paths由组装器提供，不允许另行覆盖；其他参数仅能填当前宿主工具实际支持的字段。输出规格只写比例与像素；「无独立宽高参数」等元说明写规范不写进生图正文。

## 实际发送前

```powershell
python prompt_builder.py "项目目录\工作文件\产品A\生图提示词\主图\01_初始.md"
```

读取入口校验原文、固定块和商品证据/实际附图哈希，将完整prompt及参数作为JSON输出到内存。Agent直接解析该返回对象并调用宿主图片工具，不手写、摘录或再次概括prompt，也不只把文件路径当作图像或提示词输入。无需将输出再存一批逐图JSON；内存或当前工作清单复用即可。原文、规则或输入图片已变化时拒绝读取，先核对并显式重组新任务文件，不自动改写已保存记录。

组装/读取不发起生图、不扣返修次数、不证明已发送或视觉通过；发送状态及返回文件仍按实际调用登记。该机制能约束通过此入口生成的输入完整性，不能从权限层面拦截Agent绕过入口，也不能保证模型执行全部指令。成图仍逐区检查实际产品，并汇总问题定向返修。
