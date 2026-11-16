"""Synthetic checks for catalog identity, freshness, order and incomplete entries."""
import json
from pathlib import Path
import sys
import tempfile
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from reference_catalog import build, PAGE_FIELDS, SELECTION_FIELDS

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
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
    page['order'] = 2
    save()
    assert status() == 'incomplete'
    page['order'] = 1
    save()
    Image.new('RGB', (80, 80), 'blue').save(source/'01.png')
    assert status() == 'stale'
    assert (root/'_公共参考/选套说明.md').is_file()
print('PASS: catalog keeps missing/stale entries and validates per-image identity, order and review declarations.')
