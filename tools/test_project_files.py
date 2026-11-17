"""Integration checks for file-based project operations, no image generation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image

script = Path(__file__).resolve().parents[1] / 'scripts' / 'project_files.py'

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    def invoke(operations, success=True):
        manifest = root / 'request.json'
        manifest.write_text(json.dumps({'project_root': str(root), 'operations': operations}), encoding='utf-8')
        result = subprocess.run([sys.executable, str(script), str(manifest)], capture_output=True, encoding='utf-8')
        assert (result.returncode == 0) == success, (result.stdout, result.stderr)
        return result

    large = {'copy': '商品资料' * 20000, 'history': [1]}
    (root / 'payload.json').write_text(json.dumps(large), encoding='utf-8')
    invoke([{'op': 'json', 'target': 'work/product.json', 'source': 'payload.json'}])
    target = root / 'work/product.json'
    before = target.read_bytes()
    invoke([{'op': 'json', 'target': 'work/product.json', 'data': {}, 'replace': True, 'expected_sha256': '0' * 64}], False)
    assert target.read_bytes() == before
    invoke([{'op': 'json', 'target': '../escape.json', 'data': {}}], False)
    (root / 'patch.json').write_text('{"stage_status":{"materials":"complete"}}', encoding='utf-8')
    invoke([{'op': 'json', 'target': 'work/product.json', 'source': 'patch.json', 'mode': 'merge', 'replace': True, 'expected_sha256': hashlib.sha256(before).hexdigest()}])
    updated = json.loads(target.read_text(encoding='utf-8'))
    assert updated['history'] == [1] and updated['stage_status']['materials'] == 'complete'
    Image.new('RGB', (20, 20), 'white').save(root / 'source.png')
    invoke([{'op': 'archive', 'source': 'source.png', 'target': 'work/original.png'}])
    assert (root / 'source.png').read_bytes() == (root / 'work/original.png').read_bytes()
    invoke([{'op': 'archive', 'source': 'source.png', 'target': 'work/original.png'}, {'op': 'json', 'target': 'must-not-exist.json', 'data': {}}], False)
    assert not (root / 'must-not-exist.json').exists()
    Image.new('RGB', (60, 120), 'white').save(root / 'detail-source.png')
    result = invoke([
        {'op': 'export', 'source': 'source.png', 'target': 'delivery/main/01.png', 'width': 1000, 'square': True, 'approved': True},
        {'op': 'export', 'source': 'detail-source.png', 'target': 'delivery/detail/01.png', 'width': 900, 'approved': True},
        {'op': 'preview', 'files': ['delivery/main/01.png'], 'target': 'delivery/main-preview.jpg', 'kind': 'main', 'width': 100, 'approved': True},
        {'op': 'inspect', 'files': ['delivery/main/01.png', 'delivery/detail/01.png'], 'target': 'work/export-check.json'},
        {'op': 'count', 'references': ['source.png'], 'files': ['delivery/main/01.png'], 'target': 'work/count-check.json'},
    ])
    with Image.open(root / 'delivery/detail/01.png') as image:
        assert image.size == (900, 1800)
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert records[0]['result']['upscaled'] is True and records[0]['result']['exported'] == [1000, 1000]
    Image.new('RGB', (2400, 2400), 'white').save(root / 'white-native.png')
    native_white = invoke([{'op': 'export', 'source': 'white-native.png', 'target': 'delivery/materials/white-native.png', 'width': 1000, 'square': True, 'approved': True}])
    native_result = json.loads(native_white.stdout)['result']
    assert native_result['native'] == [2400, 2400] and native_result['exported'] == [1000, 1000] and native_result['upscaled'] is False
    Image.new('RGB', (800, 800), 'white').save(root / 'white-small.png')
    small_white = invoke([{'op': 'export', 'source': 'white-small.png', 'target': 'delivery/materials/white-small.png', 'width': 1000, 'square': True, 'approved': True}])
    small_result = json.loads(small_white.stdout)['result']
    assert small_result['native'] == [800, 800] and small_result['exported'] == [1000, 1000] and small_result['upscaled'] is True
    assert len(json.loads((root / 'work/export-check.json').read_text(encoding='utf-8'))['images']) == 2
    invoke([{'op': 'export', 'source': 'source.png', 'target': 'unapproved.png', 'width': 1000}], False)
    invoke([{'op': 'export', 'source': 'detail-source.png', 'target': 'bad-square.png', 'width': 1000, 'square': True, 'approved': True}], False)
    assert not (root / 'bad-square.png').exists()
    saved = (root / 'delivery/main/01.png').read_bytes()
    invoke([{'op': 'export', 'source': 'source.png', 'target': 'delivery/main/01.png', 'width': 1000, 'approved': True, 'replace': True}], False)
    assert (root / 'delivery/main/01.png').read_bytes() == saved
    invoke([{'op': 'inspect', 'files': [], 'target': 'empty-inspect.json'}], False)
    invoke([{'op': 'count', 'references': ['source.png'], 'files': [], 'target': 'work/zero-count.json'}])
    assert json.loads((root / 'work/zero-count.json').read_text(encoding='utf-8'))['delivered_files'] == 0
    # Explicit preview selection must exclude other files in the same directory.
    Image.new('RGB', (20, 20), 'red').save(root / 'delivery/main/old.png')
    r = invoke([{'op': 'preview', 'files': ['delivery/main/01.png'], 'target': 'delivery/selected-only.jpg', 'kind': 'main', 'width': 100, 'approved': True}])
    assert json.loads(r.stdout)['result']['files_in_order'] == ['01.png']
    Image.new('RGBA', (10, 10), (255, 0, 0, 0)).save(root/'alpha.png')
    invoke([{'op': 'preview', 'files': ['alpha.png'], 'target': 'work/dark-preview.png', 'kind': 'main', 'width': 10, 'background': '#202020', 'approved': True}])
    with Image.open(root/'work/dark-preview.png') as image:
        assert image.getpixel((0, 0)) == (32, 32, 32)
    (root / 'inputs').mkdir()
    (root / 'inputs/a.png').write_bytes((root / 'source.png').read_bytes())
    (root / 'inputs/b.png').write_bytes((root / 'source.png').read_bytes())
    (root / 'inputs/facts.md').write_text('商品资料', encoding='utf-8')
    invoke([{'op': 'inventory', 'source': 'inputs', 'target': 'work/input-list.json'}])
    listing = json.loads((root / 'work/input-list.json').read_text(encoding='utf-8'))
    assert len(listing['images']) == 2 and len(listing['documents']) == 1 and len(listing['same_content_groups']) == 1
    prompt = '完整提示词\n尺寸：900×1600px；保留原商品。'
    (root / 'current-prompt.txt').write_text(prompt, encoding='utf-8')
    invoke([{'op': 'prompt', 'source': 'current-prompt.txt', 'target': 'work/prompts/detail01.md', 'tool': 'host-image-tool', 'parameters': {'transparent_background': False}}])
    assert prompt in (root / 'work/prompts/detail01.md').read_text(encoding='utf-8')
    invoke([{'op': 'prompt', 'source': 'current-prompt.txt', 'target': 'work/prompts/detail01.md', 'replace': True}], False)
    invoke([{'op': 'timing', 'target': 'work/product.json', 'stage': 'review', 'action': 'start'}, {'op': 'timing', 'target': 'work/product.json', 'stage': 'review', 'action': 'finish'}])
    timing = json.loads(target.read_text(encoding='utf-8'))['stage_timings']['review']
    assert timing['elapsed_seconds'] >= 0 and timing['status'] == 'finished'
    invoke([{'op': 'json', 'target': 'project.json', 'data': {'products': [{'name': '示例产品', 'index': 'work/product.json'}]}}])
    # A passed record with a missing actual file must not count as delivered.
    product = {'plan': {'main': ['01', '02'], 'detail': None}, 'images': {'main/01': {'status': 'passed', 'selected': 'source.png', 'delivered_from': 'source.png', 'delivered': 'work/original.png'}, 'main/02': {'status': 'passed', 'delivered': 'missing.png'}}}
    invoke([{'op': 'json', 'target': 'work/product.json', 'data': product, 'replace': True}, {'op': 'overview', 'project': 'project.json', 'target': '交付/交付总览.md'}])
    overview = (root / '交付/交付总览.md').read_text(encoding='utf-8')
    assert '1/2' in overview and '不在范围' in overview and '02' in overview and '文件不存在' in overview
    product['images']['main/01']['delivered_from'] = 'old-version.png'
    invoke([{'op': 'json', 'target': 'work/product.json', 'data': product, 'replace': True}, {'op': 'overview', 'project': 'project.json', 'target': '交付/交付总览.md', 'replace': True}])
    assert '0/2' in (root / '交付/交付总览.md').read_text(encoding='utf-8')
    invoke([{'op': 'environment', 'target': 'work/environment.json'}])
    environment = json.loads((root / 'work/environment.json').read_text(encoding='utf-8'))
    assert environment['python'] == sys.executable
    assert 'numpy_available' not in environment
print('PASS: large file input, guarded JSON merge, confinement, archive, batch export/inspect/count/selected previews, stop-on-error, timing and real-file delivery overview.')
