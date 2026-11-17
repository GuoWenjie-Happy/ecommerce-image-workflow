"""File-based project bookkeeping. Never generates, edits or approves images."""
import argparse
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from PIL import Image
import ecom_files


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Path escapes project: {value}')
    return path


def read_json(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return data


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    guard = path.with_name(path.name + '.lock')
    fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        yield
    finally:
        guard.unlink()


def atomic(path, content):
    # Caller holds the target lock. Replace only after all bytes are written.
    fd, temp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def merge(old, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(old.get(key), dict):
            merge(old[key], value)
        else:
            old[key] = value
    return old


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def input_path(root, value):
    path = Path(value)
    return path.resolve(strict=True) if path.is_absolute() else local(root, value).resolve(strict=True)


def image_files(root, values, allow_empty=False):
    if not isinstance(values, list) or (not values and not allow_empty):
        raise ValueError('An explicit nonempty image list is required')
    files = [input_path(root, value) for value in values]
    if len(set(files)) != len(files) or any(not p.is_file() or p.suffix.lower() not in ecom_files.EXTENSIONS for p in files):
        raise ValueError('Image list contains duplicates or invalid files')
    return sorted(files, key=ecom_files.natural)


def image_operation(root, target, op):
    kind = op['op']
    if kind in ('export', 'preview'):
        if op.get('approved') is not True:
            raise ValueError('Export/preview requires explicit approved selection')
        width = op.get('width', 400)
        columns = op.get('columns', 3)
        if type(width) is not int or width < 1 or type(columns) is not int or columns < 1:
            raise ValueError('Width and columns must be positive integers')
        if target.exists():
            raise ValueError('Image outputs never overwrite existing files')
        output = io.StringIO()
        with redirect_stdout(output):
            if kind == 'export':
                if 'width' not in op:
                    raise ValueError('Export requires width')
                ecom_files.export(argparse.Namespace(input=str(input_path(root, op['source'])), output=str(target), width=width, square=op.get('square', False)))
            else:
                if op.get('kind') not in ('main', 'detail'):
                    raise ValueError('Preview kind must be main or detail')
                files = image_files(root, op['files'])
                ecom_files.preview(argparse.Namespace(input=str(root), files=files, output=str(target), width=width, columns=columns, kind=op['kind'], background=op.get('background', 'white')))
        return json.loads(output.getvalue())
    if kind == 'inspect':
        data = {'images': [ecom_files.inspect(p) for p in image_files(root, op['files'])], 'visual_approval': False}
    else:
        refs, delivered = image_files(root, op['references']), image_files(root, op['files'], allow_empty=True)
        r, d = {p.stem for p in refs}, {p.stem for p in delivered}
        data = {'reference_files': len(refs), 'delivered_files': len(delivered), 'missing_ids': sorted(r-d), 'unexpected_ids': sorted(d-r), 'duplicate_reference_ids': len(refs) != len(r), 'duplicate_delivered_ids': len(delivered) != len(d)}
    atomic(target, encode(data))
    return data


def cell(value):
    return str(value).replace('|', '／').replace('\r', '').replace('\n', ' ')


def inventory(root, source):
    folder = input_path(root, source)
    if not folder.is_dir():
        raise ValueError('Inventory source must be an explicitly selected directory')
    images, documents, errors, groups = [], [], [], {}
    excluded = {'.git', '_参考缓存', '__pycache__'}
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or excluded.intersection(path.relative_to(folder).parts):
            continue
        if not path.resolve().is_relative_to(folder):
            raise ValueError('Input symlink escapes selected directory')
        name = path.relative_to(folder).as_posix()
        if path.suffix.lower() in ecom_files.EXTENSIONS:
            try:
                entry = ecom_files.inspect(path)
                entry.update(relative_path=name, sha256=digest(path))
                images.append(entry)
                groups.setdefault(entry['sha256'], []).append(name)
            except (OSError, ValueError) as exc:
                errors.append({'path': name, 'error': str(exc)})
        else:
            documents.append({'path': name, 'bytes': path.stat().st_size})
    return {'source': str(folder), 'images': images, 'documents': documents, 'errors': errors, 'same_content_groups': [names for names in groups.values() if len(names) > 1], 'note': 'File inventory only; no product facts, SKU classification or visual approval inferred.'}


def overview(root, project):
    lines = ['# 交付总览', '', f'更新时间（UTC）：{now()}', '',
             '| 产品 | 主图 已交付/应交付 | 详情 已交付/应交付 | 缺失或待核实 |',
             '|---|---|---|---|']
    issues = []
    products = project.get('products')
    if not isinstance(products, list) or not products:
        raise ValueError('Project products must be a nonempty list')
    for item in products:
        name = item.get('name', item.get('id', '未命名'))
        try:
            product = read_json(local(root, item['index']))
        except (OSError, ValueError, KeyError) as exc:
            lines.append(f'| {cell(name)} | 待核实 | 待核实 | 产品索引不可读 |')
            issues.append((name, '全部', '待核实', str(exc)))
            continue
        totals, missing = [], []
        for category, label in [('main', '主图'), ('detail', '详情')]:
            plan = product.get('plan', {})
            if category not in plan:
                totals.append('待核实')
                issues.append((name, label, '待核实', '缺少明确计划，不能猜测应交付数量'))
                missing.append(label + '计划待核实')
                continue
            ids = plan[category]
            if ids is None:
                totals.append('不在范围')
                continue
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
                raise ValueError(f'Invalid expected IDs for {name}/{category}')
            delivered = 0
            for image_id in ids:
                record = product.get('images', {}).get(f'{category}/{image_id}', {})
                reason = record.get('reason') or record.get('review', {}).get('reason')
                if record.get('status') != 'passed':
                    reason = reason or f"状态：{record.get('status', '未生成或未登记')}"
                else:
                    try:
                        path = local(root, record['delivered'])
                        with Image.open(path) as image:
                            image.verify()
                        # A delivered image must belong to the currently selected version.
                        if not record.get('selected') or record.get('delivered_from') != record['selected']:
                            raise ValueError('缺少当前选版的导出来源记录，待核实')
                        delivered += 1
                        continue
                    except FileNotFoundError:
                        reason = '交付文件不存在'
                    except (OSError, ValueError, KeyError) as exc:
                        reason = f'交付路径、文件或选版待核实：{exc}'
                missing.append(label + image_id)
                issues.append((name, label + image_id, record.get('status', '未登记'), reason))
            totals.append(f'{delivered}/{len(ids)}')
        lines.append('| ' + ' | '.join(map(cell, [name, *totals, '；'.join(missing) or '无'])) + ' |')
        for material in product.get('materials', []):
            for kind in ('white', 'transparent'):
                if material.get(kind + '_status') not in (None, 'passed'):
                    issues.append((name, f"素材{material.get('id', '')}/{kind}", material[kind + '_status'], material.get(kind + '_review', '原因未登记')))
    lines += ['', '## 未交付、待更新及待核实', '', '| 产品 | 项目 | 记录状态 | 原因 |', '|---|---|---|---|']
    lines += ['| ' + ' | '.join(map(cell, issue)) + ' |' for issue in issues]
    if not issues:
        lines.append('当前计划内主图和详情图无缺失项；本表不代替素材与视觉验收。')
    lines += ['', '说明：本表核对计划、状态和文件可读性，不执行视觉审核；预览、模糊通过项及上传限制仍须从产品记录补充。', '']
    return '\n'.join(lines).encode('utf-8')


def execute(root, op):
    target = local(root, op['target'])
    kind = op['op']
    operation_result = None
    with lock(target):
        if kind == 'timing':
            data = read_json(target)
            timings = data.setdefault('stage_timings', {})
            stage = op['stage']
            if op['action'] == 'start':
                if stage in timings:
                    raise ValueError('Stage already recorded; use a new attempt ID')
                timings[stage] = {'started_at': now(), 'status': 'running'}
            elif op['action'] == 'finish':
                entry = timings[stage]
                if entry['status'] != 'running':
                    raise ValueError('Stage is not running')
                ended = now()
                entry.update(ended_at=ended, status='finished', elapsed_seconds=(datetime.fromisoformat(ended) - datetime.fromisoformat(entry['started_at'])).total_seconds())
            else:
                raise ValueError('Timing action must be start or finish')
            atomic(target, encode(data))
        else:
            if target.exists() and not op.get('replace', False):
                raise ValueError(f'Refusing to overwrite: {target}')
            if op.get('expected_sha256') is not None and (not target.is_file() or digest(target) != op['expected_sha256']):
                raise ValueError('Target changed since read; reload before updating')
            if kind in ('export', 'preview', 'inspect', 'count'):
                operation_result = image_operation(root, target, op)
            elif kind == 'archive':
                if target.exists():
                    raise ValueError('Archive never overwrites original files')
                source = Path(op['source'])
                source = source.resolve() if source.is_absolute() else local(root, op['source'])
                if not source.is_file():
                    raise ValueError(f'Archive source missing: {source}')
                atomic(target, source.read_bytes())
                if digest(source) != digest(target):
                    raise ValueError('Archive hash mismatch')
            elif kind == 'json':
                data = read_json(local(root, op['source'])) if 'source' in op else op['data']
                if not isinstance(data, dict):
                    raise ValueError('JSON payload must be an object')
                mode = op.get('mode', 'replace')
                if mode not in ('replace', 'merge'):
                    raise ValueError('JSON mode must be replace or merge')
                if mode == 'merge':
                    data = merge(read_json(target), data)
                atomic(target, encode(data))
            elif kind == 'inventory':
                data = inventory(root, op['source'])
                atomic(target, encode(data))
                operation_result = {'images': len(data['images']), 'documents': len(data['documents']), 'errors': data['errors']}
            elif kind == 'compose':
                if target.exists():
                    raise ValueError('Composed prompt snapshots are immutable')
                from prompt_builder import build
                document = read_json(local(root, op['source']))
                spec = document
                if 'job' in op:
                    spec = {**document['jobs'][op['job']], 'identity': document['identity']}
                built = build(root, spec)
                header = '# 调用前组装记录\n\n状态：仅已组装留存，不证明调用已发送或图片已通过。\n\n组装依据及真实参数：\n' + json.dumps({k: value for k, value in built.items() if k != 'prompt'}, ensure_ascii=False, indent=2)
                atomic(target, (header+'\n\n## 完整提示词原文\n\n'+built['prompt']).encode('utf-8'))
                operation_result = {key: value for key, value in built.items() if key != 'prompt'}
            elif kind == 'prompt':
                if target.exists():
                    raise ValueError('Prompt snapshots are immutable; use a new task/attempt name')
                prompt = input_path(root, op['source']).read_text(encoding='utf-8-sig')
                if not prompt.strip():
                    raise ValueError('Prompt must not be empty')
                parameters = op.get('parameters', {})
                if not isinstance(parameters, dict):
                    raise ValueError('Parameters must be an object')
                if any(any(secret in key.lower() for secret in ('api_key', 'authorization', 'token', 'password', 'secret')) for key in parameters):
                    raise ValueError('Do not archive authentication parameters')
                prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
                header = f"# 生图调用前记录\n\n工具：{op.get('tool', '未登记')}\n状态：仅已留存，尚不证明调用已发送或返回。\n提示词SHA-256：{prompt_hash}\n\n实际参数：\n" + json.dumps(parameters, ensure_ascii=False, indent=2) + '\n\n## 完整提示词原文\n\n'
                atomic(target, (header + prompt).encode('utf-8'))
                operation_result = {'prompt_sha256': prompt_hash, 'call_status': 'not_verified'}
            elif kind == 'overview':
                atomic(target, overview(root, read_json(local(root, op['project']))))
            elif kind == 'environment':
                atomic(target, encode({'python': sys.executable, 'python_version': sys.version, 'checked_at': now(), 'pillow': Image.__version__, 'project_root': str(root)}))
            else:
                raise ValueError(f'Unknown operation: {kind}')
    result = {'op': kind, 'target': str(target), 'status': 'completed', 'sha256': digest(target)}
    if operation_result is not None:
        result['result'] = operation_result
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    request = read_json(args.manifest)
    root = Path(request['project_root']).resolve(strict=True)
    operations = request['operations']
    if not root.is_dir() or not isinstance(operations, list) or not operations:
        raise ValueError('Expected existing project directory and nonempty operations')
    for index, op in enumerate(operations):
        try:
            result = execute(root, op)
            print(json.dumps({'index': index, **result}, ensure_ascii=False), flush=True)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            print(json.dumps({'index': index, 'op': op.get('op'), 'target': op.get('target'), 'status': 'failed', 'error': str(exc), 'remaining': 'not executed'}, ensure_ascii=False), flush=True)
            return 1
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
