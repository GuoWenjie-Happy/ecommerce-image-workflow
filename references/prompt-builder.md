# 产品保真提示词组装

本流程的新增白底、透明底、营销图与返修调用使用project_files.py的compose操作。固定条款来自 [product-preservation.txt](product-preservation.txt)，由脚本原文追加；AI只填写商品观察及本张设计，不自行压缩成“只保留品牌、品名、容量”。第三方原文件不修改。

## 商品观察表

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
  "copy": "<全部准确新增文案；无字时明确写无新增文案>",
  "constraints": "<本张限制>",
  "parameters": {"transparent_background": false}
}
```

stage允许white、transparent、main、detail、repair。出镜商品必须附product角色图；返修必须附edit_target当前编辑图。其他角色为design和identity_check。明确不出镜时仍要附参考，product_visible为false并填absence_reason，不能生成另一种包装凑版。素材阶段不允许不出镜。

各阶段references必须落实真实用途：白底用对应原照作product，透明底用已验收白底，营销图用匹配高清白底/透明底；source_images用于追溯商品原证据，不会自动全部附入模型。scripts只检查角色存在、路径可读，不能判断选错SKU、附图是不是已验收或角色是否写错。

在项目操作清单中逐图或批量添加：

```json
{"op":"compose","source":"工作文件/产品A/执行卡.json","job":"main/01","target":"工作文件/产品A/生图提示词/主图/01_初始.md"}
```

固定块、观察表、尺寸及逐图设计被确定性组装，文件同时记录参数、来源与附图哈希，以及policy/identity/prompt哈希。参数中的prompt和referenced_image_paths由组装器提供，不允许另行覆盖；其他参数仅能填当前宿主工具实际支持的字段。尺寸只写output_spec时不是独立宽高参数，不能伪记为强制尺寸。

## 实际发送前

```powershell
python prompt_builder.py "项目目录\工作文件\产品A\生图提示词\主图\01_初始.md"
```

读取入口校验原文、固定块和商品证据/实际附图哈希，将完整prompt及参数作为JSON输出到内存。Agent直接解析该返回对象并调用宿主图片工具，不手写、摘录或再次概括prompt，也不只把文件路径当作图像或提示词输入。无需将输出再存一批逐图JSON；内存或当前工作清单复用即可。原文、规则或输入图片已变化时拒绝读取，先核对并显式重组新任务文件，不自动改写已保存记录。

组装/读取不发起生图、不扣返修次数、不证明已发送或视觉通过；发送状态及返回文件仍按实际调用登记。该机制能约束通过此入口生成的输入完整性，不能从权限层面拦截Agent绕过入口，也不能保证模型执行全部指令。成图仍逐区检查实际产品，并汇总问题定向返修。
