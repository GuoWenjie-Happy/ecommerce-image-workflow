"""Deterministic preservation prompt assembly; no image generation or OCR."""
import hashlib
import json
import argparse
import sys
from pathlib import Path
from PIL import Image

FIELDS = ('shape_proportions', 'structure', 'colors_materials', 'graphics_patterns', 'text_regions', 'accessories')
FIELD_LABELS = {
    'shape_proportions': '外形比例',
    'structure': '结构部件',
    'colors_materials': '颜色材质',
    'graphics_patterns': '图案标识',
    'text_regions': '包装与本体文字',
    'accessories': '附件与拍摄道具',
}
FIXED = Path(__file__).resolve().parents[1] / 'references' / 'product-preservation.txt'


PLACEHOLDERS = ('同上', '…', '...', '待填写', '待补充', '待补', 'TBD', 'tbd')

# 成图禁词：命中则 compose 失败（可进交付说明，不可进上图文字）
FORBIDDEN_COPY_MARKERS = (
    '资料来源', '文案溯源', '产品保真', '商品保真', '执行备注',
    '准确文案', 'copy_units', '来源：', '来源:', 'http://', 'https://',
)


def text(value, field):
    if not isinstance(value, str) or not value.strip() or value.strip() in PLACEHOLDERS:
        raise ValueError(f'Missing or placeholder text: {field}')
    return value.strip()


def reject_forbidden_copy(blob, field):
    """图内文案不得含来源脚注/元标记/保真条款泄漏。"""
    if not isinstance(blob, str) or not blob:
        return
    for marker in FORBIDDEN_COPY_MARKERS:
        if marker in blob:
            raise ValueError(
                f'{field} 含成图禁词「{marker}」：请删来源/溯源/保真元句，仅保留消费者向文案')


def validate_copy_units(spec):
    """密文页硬闸：每个信息位须有完整可上图标题+说明；缺说明不得组装生图。"""
    stage = spec.get('stage')
    if stage not in ('main', 'detail', 'repair'):
        return
    units = spec.get('copy_units')
    dense = spec.get('dense_copy') is True
    if dense and not units:
        raise ValueError('密文页 dense_copy=true 须提供 copy_units（每格标题+说明）')
    if units is None:
        return
    if not isinstance(units, list) or not units:
        raise ValueError('copy_units 须为非空数组')
    for i, unit in enumerate(units):
        if not isinstance(unit, dict):
            raise ValueError(f'copy_units[{i}] 须为对象')
        title = text(unit.get('title'), f'copy_units[{i}].title')
        reject_forbidden_copy(title, f'copy_units[{i}].title')
        if unit.get('title_only') is True:
            continue
        body = text(unit.get('body'), f'copy_units[{i}].body')
        reject_forbidden_copy(body, f'copy_units[{i}].body')


def validate_job_gates(spec, roles, references):
    """生图前硬闸：套框安全区、对照、图标、多窗、信任页附图。"""
    stage = spec.get('stage')
    if stage not in ('main', 'detail', 'repair'):
        return
    reject_forbidden_copy(spec.get('copy') or '', 'copy')
    if spec.get('uses_brand_frame') is True:
        safe = spec.get('safe_area')
        layout = spec.get('layout') or ''
        if safe is None and '安全区' not in layout:
            raise ValueError('套框张 uses_brand_frame=true 须提供 safe_area 或在 layout 写明安全区')
    layout = spec.get('layout') or ''
    if spec.get('physical_scale') is True:
        align = spec.get('scale_alignment')
        if not isinstance(align, str) or not align.strip():
            raise ValueError('physical_scale=true 须提供 scale_alignment（共面/对齐说明）')
    else:
        for bad in ('硬币', '直尺', '钢蹦', '一元币'):
            if bad in layout:
                raise ValueError(
                    f'未开启实物对照时构图不得点名「{bad}」；分级/克重页默认纯表')
    if spec.get('icon_list') is True and spec.get('icon_uniform') is not True:
        raise ValueError('参数/对勾列表页 icon_list=true 须声明 icon_uniform=true')
    if spec.get('multi_panel') is True:
        count = spec.get('panel_count')
        if not isinstance(count, int) or count < 2:
            raise ValueError('multi_panel=true 须提供 panel_count（≥2 的整数）')
    page_kind = str(spec.get('page_kind') or '').lower()
    if page_kind in ('trust', 'cert', 'certificate', '证明', '信任'):
        seal_hints = ('证书', '检测报告', 'sgs', '章面', '公章', '报告表')
        for item in references:
            if item.get('role') != 'design':
                continue
            path_l = str(item.get('path') or '').lower()
            for hint in seal_hints:
                if hint.lower() in path_l or hint in str(item.get('path') or ''):
                    raise ValueError(
                        '信任/证明页不得附带证书/章面/报告类 design 参考；'
                        '改用不含章结构示意或仅本品白底+信息卡')


def format_copy_units(units):
    lines = ['上图文字分位（须逐字印上图；无对应文字的说明区须留白或删层，禁止自撰）：']
    for i, unit in enumerate(units, 1):
        label = unit.get('id') or str(i)
        if unit.get('title_only') is True:
            lines.append(f'{label} 标题：{unit["title"].strip()}')
        else:
            lines.append(
                f'{label} 标题：{unit["title"].strip()}；说明：{unit["body"].strip()}')
    return '\n'.join(lines)


def format_product_identity(fields, visible):
    """
    生图用短「商品核对」：从六类观察各抽一句，硬要求只写一遍。
    完整观察表与保真全文仍在执行卡/仓库归档；本函数才进默认生图串。
    """
    lines = [
        '商品核对（以商品附图为准；与附图冲突时以附图可见为准）：'
    ]
    for key in FIELDS:
        entry = fields[key]
        status = entry['status']
        desc = text(entry.get('description'), key)
        label = FIELD_LABELS[key]
        if status == 'observed':
            lines.append(f'- {label}：{desc}')
        elif status == 'not_visible':
            lines.append(f'- {label}：原图未见——{desc}；不要凭空补画或编造')
        else:
            lines.append(f'- {label}：不适用——{desc}；不要强加')
    lines.append('硬要求：')
    if visible:
        lines.append(
            '- 本张商品须出镜，以 product 附图为据；'
            '按附图保留外形、比例、颜色、可见结构与信息布局。')
    else:
        lines.append(
            '- 本张明确不出镜：不要添加商品、包装或易混淆的替代物。')
    lines.append(
        '- 包装/本体可读文字不改、不增、不删、不涂平；'
        '不可读小字保持模糊占位，不猜写；原有图案徽记按实物，不放大成新背书。')
    lines.append(
        '- 不新增或拼接不存在的部件/印花/附件/包装；拍摄道具不要画成随货。')
    lines.append(
        '- 参考海报只学版式与构图，不要为迁就参考改商品本身；'
        '可调位置、整体尺度与光影，不要改商品自身比例，不要补看不见的背面。')
    lines.append(
        '- 画面新增字只用下面「上图文字」/分位；核对说明不要印进画面。')
    return '\n'.join(lines)


def format_legacy_observation(descriptions):
    return (
        '商品观察表（observed为已观察；其他项只记录原因，不得据此补造）：\n'
        + '\n'.join(descriptions)
    )


def image_path(root, name):
    path = Path(name)
    if not path.is_absolute():
        path = (root / path).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Image path escapes project')
    path = path.resolve(strict=True)
    with Image.open(path) as image:
        image.verify()
    return path


def reject_credentials(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if any(word in key.lower() for word in (
                    'api_key', 'apikey', 'authorization', 'token', 'password', 'secret')):
                raise ValueError('Authentication parameters cannot be archived')
            reject_credentials(item)
    elif isinstance(value, list):
        for item in value:
            reject_credentials(item)


def build(root, spec):
    stage = spec['stage']
    if stage not in ('white', 'transparent', 'main', 'detail', 'repair'):
        raise ValueError('Unsupported generation stage')
    visible = spec['product_visible']
    if type(visible) is not bool or (not visible and stage in ('white', 'transparent')):
        raise ValueError('Product visibility must be explicit; materials require product')
    identity = spec['identity']
    product_id = text(identity['product_id'], 'product_id')
    sources = identity['source_images']
    if not isinstance(sources, list) or not sources:
        raise ValueError('Identity requires source image evidence')
    source_records = []
    for source in sources:
        path = image_path(root, source)
        source_records.append({
            'path': str(path),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    fields = identity['fields']
    if not isinstance(fields, dict) or set(fields) != set(FIELDS):
        raise ValueError('Identity must contain all six preservation fields')
    descriptions = []
    for key in FIELDS:
        entry = fields[key]
        if not isinstance(entry, dict) or entry.get('status') not in (
                'observed', 'not_visible', 'not_applicable'):
            raise ValueError(f'Invalid observation status: {key}')
        descriptions.append(
            f"{key} [{entry['status']}]：{text(entry.get('description'), key)}")
    references = spec['references']
    if not isinstance(references, list) or not references:
        raise ValueError('Explicit reference image list is required')
    roles, images, captions = [], [], []
    for n, item in enumerate(references, 1):
        role = item['role']
        if role not in ('product', 'design', 'edit_target', 'identity_check'):
            raise ValueError('Unknown image role')
        images.append(str(image_path(root, item['path'])))
        roles.append(role)
        captions.append(f'输入图{n}职责：{role}')
    if visible and 'product' not in roles:
        raise ValueError('Visible product requires a product reference')
    if stage == 'repair' and 'edit_target' not in roles:
        raise ValueError('Repair requires the actual edit target')
    validate_copy_units(spec)
    validate_job_gates(spec, roles, references)

    fixed = FIXED.read_text(encoding='utf-8-sig').strip()
    if not fixed:
        raise ValueError('Fixed preservation policy is missing')

    # 默认：短「商品核对」；legacy：整表观察+保真全文（仓库仍保留原文，测试不好可改回）
    legacy = spec.get('full_legacy_preservation_prompt') is True
    prompt_mode = 'legacy_full' if legacy else 'identity_brief'

    sections = [
        f'任务阶段：{stage}；商品ID：{product_id}。',
        '输出规格：' + text(spec.get('output_spec'), 'output_spec'),
        '\n'.join(captions),
    ]
    if legacy:
        sections.append(format_legacy_observation(descriptions))
    else:
        sections.append(format_product_identity(fields, visible))
    sections.append(
        '商品出镜：' + (
            '是' if visible
            else '否；原因：' + text(spec.get('absence_reason'), 'absence_reason')))

    has_units = isinstance(spec.get('copy_units'), list) and bool(spec['copy_units'])
    for key, label in [
            ('style', '本产品风格'), ('layout', '本张构图'),
            ('copy', '上图文字'), ('constraints', '本张限制')]:
        if key == 'copy' and has_units:
            raw = spec.get('copy')
            if isinstance(raw, str) and raw.strip():
                reject_forbidden_copy(raw, 'copy')
            sections.append('上图文字：见下方分位（须逐字上图），此处不重复摘要。')
            continue
        sections.append(label + '：' + text(spec.get(key), key))
    if has_units:
        sections.append(format_copy_units(spec['copy_units']))
        sections.append(
            '禁止模型补字：图内新增文字只能逐字使用上方分位句子；'
            '说明区无对应文字则留白或删该说明层，禁止自撰。')
    if legacy:
        sections.append(fixed)

    prompt = '\n\n'.join(sections)
    parameters = dict(spec.get('parameters', {}))
    if ('referenced_image_paths' in parameters
            or 'num_last_images_to_include' in parameters
            or 'prompt' in parameters):
        raise ValueError('Prompt and references must come from the assembled fields')
    reject_credentials(parameters)
    parameters['referenced_image_paths'] = images
    return {
        'prompt': prompt,
        'parameters': parameters,
        'source_evidence': source_records,
        'reference_evidence': [
            {'path': name,
             'sha256': hashlib.sha256(Path(name).read_bytes()).hexdigest()}
            for name in images],
        'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'policy_sha256': hashlib.sha256(fixed.encode('utf-8')).hexdigest(),
        'identity_sha256': hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True).encode('utf-8')
        ).hexdigest(),
        'prompt_mode': prompt_mode,
    }


def load_request(path):
    content = path.read_text(encoding='utf-8')
    before, separator, prompt = content.partition('\n\n## 完整提示词原文\n\n')
    if not separator:
        raise ValueError('Not a composed prompt snapshot')
    metadata = json.loads(before.split('组装依据及真实参数：\n', 1)[1])
    fixed = FIXED.read_text(encoding='utf-8-sig').strip()
    if hashlib.sha256(prompt.encode('utf-8')).hexdigest() != metadata['prompt_sha256']:
        raise ValueError('Prompt changed after composition')
    mode = metadata.get('prompt_mode')
    if mode is None:
        # 旧快照无字段：有全文保真块则按 legacy 校验
        mode = 'legacy_full' if '商品保真固定条款' in prompt else 'identity_brief'
    if mode == 'legacy_full':
        if (metadata['policy_sha256']
                != hashlib.sha256(fixed.encode('utf-8')).hexdigest()
                or not prompt.endswith(fixed)):
            raise ValueError(
                'Preservation policy changed; explicitly recompose before new generation')
    else:
        if '商品核对' not in prompt and '商品身份' not in prompt:
            raise ValueError('Identity brief missing; explicitly recompose before new generation')
        # 归档保真文件仍参与哈希登记；文件被改时要求重组装，便于与仓库记录对齐
        if metadata['policy_sha256'] != hashlib.sha256(fixed.encode('utf-8')).hexdigest():
            raise ValueError(
                'Archived preservation file changed; explicitly recompose before new generation')
    for item in metadata['source_evidence'] + metadata['reference_evidence']:
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Source product evidence changed; recheck identity before generation')
    reject_credentials(metadata['parameters'])
    for image in metadata['parameters']['referenced_image_paths']:
        with Image.open(image) as reference:
            reference.verify()
    return {'prompt': prompt, **metadata['parameters']}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(
        description='Read and validate an assembled host image request; does not send it.')
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(load_request(args.snapshot), ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
