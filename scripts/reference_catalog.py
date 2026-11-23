"""Refresh suite caches and build a selection catalog from AI-authored analyses."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from project_files import atomic, encode, lock, now, read_json
from reference_cache import prepare, relative_location

PAGE_FIELDS = ('content', 'purchase_task', 'expression', 'image_text_relation',
               'composition', 'transfer', 'uncertainties')
SELECTION_FIELDS = ('product_forms', 'design_features', 'modules',
                    'required_materials', 'adjustable_items')


def assess(cache, kind, record):
    path = cache/(kind+'_analysis.json')
    result = {'status': 'missing', 'analysis_file': str(path)}
    if not path.is_file():
        return result
    try:
        data = read_json(path)
        if data.get('source_fingerprint') != record['fingerprint'] or data.get('rules_version') != record['analysis_rules_version']:
            return {**result, 'status': 'stale'}
        analysis = data['analysis']
        pages = analysis['pages']
        if len(pages) != len(record['files']):
            raise ValueError('Page count differs from source')
        for order, (page, source) in enumerate(zip(pages, record['files']), 1):
            if page['path'] != source['path'] or page['sha256'] != source['sha256'] or page['order'] != order:
                raise ValueError('Page identity or order differs from source')
            if any(not isinstance(page.get(key), str) or not page[key].strip() for key in PAGE_FIELDS):
                raise ValueError('Incomplete page analysis')
        selection = analysis['selection']
        if any(not isinstance(selection.get(key), str) or not selection[key].strip() for key in SELECTION_FIELDS):
            raise ValueError('Incomplete selection summary')
        if not isinstance(analysis.get('suite_style'), str) or not analysis['suite_style'].strip():
            raise ValueError('Missing suite style')
        review = analysis.get('review', {})
        if review.get('status') != 'passed' or not review.get('checked_paths') or not set(review['checked_paths']) <= {f['path'] for f in record['files']}:
            raise ValueError('Missing valid visual spot-check record')
        return {**result, 'status': 'ready', 'selection': selection,
                'suite_style': analysis['suite_style'], 'page_count': len(pages)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {**result, 'status': 'incomplete', 'reason': str(exc)}


def build(request):
    root = Path(request['root']).resolve(strict=True)
    sets = request['sets']
    if not root.is_dir() or not isinstance(sets, list) or not sets:
        raise ValueError('Expected reference library root and nonempty complete suite registry')
    rows, seen = [], set()
    for spec in sets:
        suite = (root/spec['suite']).resolve(strict=True)
        if not suite.is_relative_to(root) or suite == root or '_公共参考' in suite.relative_to(root).parts:
            raise ValueError('Suite must be inside library and outside public catalog')
        if suite in seen:
            raise ValueError('Duplicate suite')
        seen.add(suite)
        with redirect_stdout(io.StringIO()):
            prepared = prepare({**spec, 'root': str(suite)})
        categories = {kind: {**assess(Path(prepared['cache']), kind, record),
                             'fingerprint': record['fingerprint'],
                             'duplicate_ids': record['duplicate_ids']}
                      for kind, record in prepared['categories'].items()}
        for entry in categories.values():
            entry['analysis_file'], entry['analysis_file_external'] = relative_location(Path(entry['analysis_file']), root)
        cache_path, cache_external = relative_location(Path(prepared['cache']), root)
        rows.append({'suite': suite.relative_to(root).as_posix(), 'cache': cache_path, 'cache_external': cache_external,
                     'categories': categories})
    catalog = {'schema_version': 2, 'source': '.', 'path_base': 'reference_library', 'checked_at': now(),
               'scope': 'manifest_sets', 'suites': rows}
    output = root/'_公共参考'
    if not output.resolve().is_relative_to(root):
        raise ValueError('Public catalog symlink escapes library')
    with lock(output/'选套索引.json'):
        atomic(output/'选套索引.json', encode(catalog))
        lines = ['# 参考选套索引', '', '由各套系分析汇总；ready仅表示记录结构和指纹有效，不证明AI观察正确。', '',
                 '路径相对于当前参考库根目录（本文件所在_公共参考目录的上一级）；外置缓存须另行提供。', '',
                 '范围以本次清单为准；未登记套系不在此索引内。', '']
        for row in rows:
            lines += ['## '+row['suite'], '']
            for kind, entry in row['categories'].items():
                lines += [f"- {kind}: {entry['status']}"]
                if entry['status'] == 'ready':
                    for key, value in entry['selection'].items():
                        lines.append(f'  - {key}: {value}')
            lines.append('')
        atomic(output/'选套说明.md', ('\n'.join(lines)+'\n').encode('utf-8'))
    return catalog


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        result = build(read_json(args.manifest))
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
