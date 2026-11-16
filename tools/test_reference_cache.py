"""Cache invalidation checks using temporary synthetic reference fixtures."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image

script = Path(__file__).resolve().parents[1]/'scripts'/'reference_cache.py'
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    suite = root/'suite'
    for kind in ('main', 'detail'):
        (suite/kind).mkdir(parents=True)
        Image.new('RGB', (100, 160), 'white').save(suite/kind/'01.png')
    def run(categories, version='1'):
        request = root/'request.json'
        request.write_text(json.dumps({'sets': [{'root': str(suite), 'categories': categories, 'analysis_rules_version': version}]}), encoding='utf-8')
        r = subprocess.run([sys.executable, str(script), str(request)], capture_output=True, encoding='utf-8')
        assert r.returncode == 0, (r.stdout, r.stderr)
        return json.loads(r.stdout)['categories']
    first = run({'main': 'main', 'detail': 'detail'})
    assert first['main']['updated'] and first['detail']['updated']
    assert first['detail']['files'][0]['width'] == 100
    assert first['main']['changes']['added'] == ['main/01.png']
    original = (suite/'main/01.png').read_bytes()
    hit = run({'main': 'main', 'detail': 'detail'})
    assert not hit['main']['updated'] and not hit['detail']['updated']
    assert not hit['main']['changes']['modified'] and not hit['main']['changes']['added']
    (suite/'_参考缓存/main_analysis.json').write_text(json.dumps({'source_fingerprint': hit['main']['fingerprint'], 'rules_version': '1', 'analysis': {'layout': 'fixture'}}), encoding='utf-8')
    assert not run({'main': 'main'})['main']['analysis_required']
    changed_rules = run({'main': 'main'}, version='2')['main']
    assert not changed_rules['updated'] and changed_rules['analysis_required']
    Image.new('RGB', (100, 160), 'red').save(suite/'detail/01.png')
    changed = run({'detail': 'detail'})
    assert changed['detail']['updated'] and set(changed) == {'detail'}
    assert changed['detail']['changes']['modified'] == ['detail/01.png']
    index = json.loads((suite/'_参考缓存/index.json').read_text(encoding='utf-8'))
    assert 'main' in index['categories']
    preview = suite/'_参考缓存'/index['categories']['detail']['preview']
    preview.write_bytes(b'broken')
    assert run({'detail': 'detail'})['detail']['updated']
    assert (suite/'main/01.png').read_bytes() == original
    (suite/'detail/02.png').write_bytes((suite/'detail/01.png').read_bytes())
    assert len(run({'detail': 'detail'})['detail']['files']) == 2
    (suite/'detail/01.png').unlink()
    deleted = run({'detail': 'detail'})['detail']
    assert len(deleted['files']) == 1 and deleted['updated']
    assert deleted['changes']['removed'] == ['detail/01.png']
    # Scanning twice must not forget outstanding analysis changes.
    baseline = run({'detail': 'detail'})['detail']
    (suite/'_参考缓存/detail_analysis.json').write_text(json.dumps({'source_fingerprint': baseline['fingerprint'], 'rules_version': '1', 'analysis': {'layout': 'fixture'}}), encoding='utf-8')
    assert run({'detail': 'detail'})['detail']['analysis_scope'] == 'none'
    Image.new('RGB', (100, 160), 'blue').save(suite/'detail/02.png')
    pending = run({'detail': 'detail'})['detail']
    assert pending['analysis_scope'] == 'incremental' and pending['analysis_changes']['modified'] == ['detail/02.png']
    again = run({'detail': 'detail'})['detail']
    assert again['changes']['modified'] == [] and again['analysis_changes']['modified'] == ['detail/02.png']
    (suite/'_参考缓存/detail_analysis.json').write_text(json.dumps({'source_fingerprint': again['fingerprint'], 'rules_version': '1', 'analysis': {'layout': 'updated fixture'}}), encoding='utf-8')
    accepted = run({'detail': 'detail'})['detail']
    assert accepted['analysis_scope'] == 'none' and not accepted['analysis_changes']['modified']
    rules = run({'detail': 'detail'}, version='2')['detail']
    assert rules['analysis_scope'] == 'full' and not rules['updated']
    (suite/'_参考缓存/detail_analysis.json').write_text('{broken', encoding='utf-8')
    assert run({'detail': 'detail'})['detail']['analysis_scope'] == 'full'
print('PASS: reference batch metadata, cache hits, content changes, corruption, deletion, category isolation and no reference deduplication.')
