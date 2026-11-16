"""Deterministic preservation prompt assembly; no image generation or OCR."""
import hashlib
import json
import argparse
import sys
from pathlib import Path
from PIL import Image

FIELDS = ('shape_proportions', 'structure', 'colors_materials', 'graphics_patterns', 'text_regions', 'accessories')
FIXED = Path(__file__).resolve().parents[1]/'references'/'product-preservation.txt'


def text(value, field):
    if not isinstance(value, str) or not value.strip() or value.strip() in ('同上', '…', '...', '待填写', '待补充'):
        raise ValueError(f'Missing or placeholder text: {field}')
    return value.strip()


def image_path(root, name):
    path = Path(name)
    if not path.is_absolute():
        path = (root/path).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Image path escapes project')
    path = path.resolve(strict=True)
    with Image.open(path) as image:
        image.verify()
    return path


def reject_credentials(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if any(word in key.lower() for word in ('api_key', 'apikey', 'authorization', 'token', 'password', 'secret')):
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
        source_records.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    fields = identity['fields']
    if not isinstance(fields, dict) or set(fields) != set(FIELDS):
        raise ValueError('Identity must contain all six preservation fields')
    descriptions = []
    for key in FIELDS:
        entry = fields[key]
        if not isinstance(entry, dict) or entry.get('status') not in ('observed', 'not_visible', 'not_applicable'):
            raise ValueError(f'Invalid observation status: {key}')
        descriptions.append(f"{key} [{entry['status']}]：{text(entry.get('description'), key)}")
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
    sections = [f"任务阶段：{stage}；商品ID：{product_id}。", '输出规格：'+text(spec.get('output_spec'), 'output_spec'), '\n'.join(captions),
                '商品观察表（observed为已观察；其他项只记录原因，不得据此补造）：\n'+'\n'.join(descriptions),
                '商品出镜：'+('是' if visible else '否；原因：'+text(spec.get('absence_reason'), 'absence_reason'))]
    for key, label in [('style', '本产品风格'), ('layout', '本张构图'), ('copy', '准确新增文案'), ('constraints', '本张限制')]:
        sections.append(label+'：'+text(spec.get(key), key))
    fixed = FIXED.read_text(encoding='utf-8-sig').strip()
    if not fixed:
        raise ValueError('Fixed preservation policy is missing')
    sections.append(fixed)
    prompt = '\n\n'.join(sections)
    parameters = dict(spec.get('parameters', {}))
    if 'referenced_image_paths' in parameters or 'num_last_images_to_include' in parameters or 'prompt' in parameters:
        raise ValueError('Prompt and references must come from the assembled fields')
    reject_credentials(parameters)
    parameters['referenced_image_paths'] = images
    return {'prompt': prompt, 'parameters': parameters, 'source_evidence': source_records,
            'reference_evidence': [{'path': name, 'sha256': hashlib.sha256(Path(name).read_bytes()).hexdigest()} for name in images],
            'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
            'policy_sha256': hashlib.sha256(fixed.encode('utf-8')).hexdigest(),
            'identity_sha256': hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()}


def load_request(path):
    content = path.read_text(encoding='utf-8')
    before, separator, prompt = content.partition('\n\n## 完整提示词原文\n\n')
    if not separator:
        raise ValueError('Not a composed prompt snapshot')
    metadata = json.loads(before.split('组装依据及真实参数：\n', 1)[1])
    fixed = FIXED.read_text(encoding='utf-8-sig').strip()
    if hashlib.sha256(prompt.encode('utf-8')).hexdigest() != metadata['prompt_sha256']:
        raise ValueError('Prompt changed after composition')
    if metadata['policy_sha256'] != hashlib.sha256(fixed.encode('utf-8')).hexdigest() or not prompt.endswith(fixed):
        raise ValueError('Preservation policy changed; explicitly recompose before new generation')
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
    parser = argparse.ArgumentParser(description='Read and validate an assembled host image request; does not send it.')
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(load_request(args.snapshot), ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
