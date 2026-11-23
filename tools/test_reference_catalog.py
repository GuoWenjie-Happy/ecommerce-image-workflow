"""Synthetic checks for catalog identity, freshness, order and incomplete entries."""
import json
import shutil
from pathlib import Path
import sys
import tempfile
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reference_catalog import build, PAGE_FIELDS, SELECTION_FIELDS

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)/'library'
    source = root/'fruit'/'suite'/'main'
    source.mkdir(parents=True)
    Image.new('RGB', (80, 80), 'white').save(source/'01.png')
    request = {'root': str(root), 'sets': [{'suite': 'fruit/suite', 'categories': {'main': 'main'}}]}
    first = build(request)
    assert first['suites'][0]['categories']['main']['status'] == 'missing'
    cache = root/'fruit/suite/_参考缓存'
    record = json.loads((cache/'index.json').read_text(encoding='utf-8'))['categories']['main']
    page = {**{key: 'fixture observation' for key in PAGE_FIELDS},
            'path': 'main/01.png', 'sha256': record['files'][0]['sha256'], 'order': 1}
    analysis = {'source_fingerprint': record['fingerprint'], 'rules_version': '1',
                'analysis': {'pages': [page], 'suite_style': 'fixture style',
                             'selection': {key: 'fixture summary' for key in SELECTION_FIELDS},
                             'review': {'status': 'passed', 'checked_paths': ['main/01.png']}}}
    def save():
        (cache/'main_analysis.json').write_text(json.dumps(analysis), encoding='utf-8')
    def status():
        return build(request)['suites'][0]['categories']['main']['status']
    save()
    assert status() == 'ready'
    catalog = build(request)
    entry = catalog['suites'][0]
    assert catalog['source'] == '.' and catalog['path_base'] == 'reference_library'
    assert entry['cache'] == 'fruit/suite/_参考缓存'
    assert entry['categories']['main']['analysis_file'] == 'fruit/suite/_参考缓存/main_analysis.json'
    assert str(root) not in (root/'_公共参考/选套索引.json').read_text(encoding='utf-8')
    analysis_bytes = (cache/'main_analysis.json').read_bytes()
    overview_bytes = (cache/'main_overview.jpg').read_bytes()
    # Copy the complete library elsewhere, retaining cache and analysis files.
    relocated = Path(tmp)/'relocated'
    shutil.copytree(root, relocated)
    moved_request = {**request, 'root': str(relocated)}
    moved = build(moved_request)
    assert moved['suites'][0]['categories']['main']['status'] == 'ready'
    moved_cache = relocated/'fruit/suite/_参考缓存'
    assert (moved_cache/'main_analysis.json').read_bytes() == analysis_bytes
    assert (moved_cache/'main_overview.jpg').read_bytes() == overview_bytes
    # Old absolute sources from another OS migrate only after content checks.
    legacy_index = json.loads((moved_cache/'index.json').read_text(encoding='utf-8'))
    legacy_index.update(schema_version=1, source='/Users/old-machine/library/fruit/suite')
    (moved_cache/'index.json').write_text(json.dumps(legacy_index), encoding='utf-8')
    assert build(moved_request)['suites'][0]['categories']['main']['status'] == 'ready'
    migrated = json.loads((moved_cache/'index.json').read_text(encoding='utf-8'))
    assert migrated['source'] == '..' and migrated['schema_version'] == 2
    assert (moved_cache/'main_analysis.json').read_bytes() == analysis_bytes
    # Mismatched relocation is rejected without rewriting the cache index.
    (moved_cache/'index.json').write_text(json.dumps(legacy_index), encoding='utf-8')
    before = (moved_cache/'index.json').read_bytes()
    Image.new('RGB', (80, 80), 'red').save(relocated/'fruit/suite/main/01.png')
    try:
        build(moved_request)
        raise AssertionError('Mismatched legacy cache accepted')
    except ValueError as exc:
        assert 'Legacy relocation source differs' in str(exc)
    assert (moved_cache/'index.json').read_bytes() == before
    page['order'] = 2
    save()
    assert status() == 'incomplete'
    page['order'] = 1
    save()
    Image.new('RGB', (80, 80), 'blue').save(source/'01.png')
    assert status() == 'stale'
    assert (root/'_公共参考/选套说明.md').is_file()
print('PASS: catalog validity, relative links, moved-library reuse, cross-OS legacy migration and mismatch rejection.')
