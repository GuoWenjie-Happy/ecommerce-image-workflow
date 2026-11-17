"""Ensure mandatory preservation instructions survive prompt assembly."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image

script = Path(__file__).resolve().parents[1]/'scripts'/'project_files.py'
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    Image.new('RGB', (20, 20), 'white').save(root/'product.png')
    fields = ('shape_proportions', 'structure', 'colors_materials', 'graphics_patterns', 'text_regions', 'accessories')
    identity = {'product_id': 'fixture-product', 'source_images': ['product.png'], 'fields': {key: {'status': 'observed', 'description': '原图观察到的测试特征，不作真实商品证据'} for key in fields}}
    spec = {'identity': identity, 'stage': 'main', 'product_visible': True, 'output_spec': '1000×1000px，1:1', 'references': [{'path': 'product.png', 'role': 'product'}], 'style': '浅色背景', 'layout': '完整商品居中', 'copy': '测试文字', 'constraints': '不增加道具', 'parameters': {'transparent_background': False}}
    def run(data, filename, ok=True):
        (root/'spec.json').write_text(json.dumps(data), encoding='utf-8')
        request = {'project_root': str(root), 'operations': [{'op': 'compose', 'source': 'spec.json', 'target': filename}]}
        (root/'request.json').write_text(json.dumps(request), encoding='utf-8')
        r = subprocess.run([sys.executable, str(script), str(root/'request.json')], capture_output=True, encoding='utf-8')
        assert (r.returncode == 0) == ok, (r.stdout, r.stderr)
        return r
    a = run(spec, 'prompts/main01.md')
    text = (root/'prompts/main01.md').read_text(encoding='utf-8')
    assert '不猜写、不删除、不涂平' in text and 'text_regions' in text
    b = run(spec, 'prompts/main02.md')
    assert json.loads(a.stdout)['result']['prompt_sha256'] == json.loads(b.stdout)['result']['prompt_sha256']
    reader = script.parent/'prompt_builder.py'
    read = subprocess.run([sys.executable, str(reader), str(root/'prompts/main01.md')], capture_output=True, encoding='utf-8')
    assert read.returncode == 0, read.stderr
    request = json.loads(read.stdout)
    assert request['prompt'] == text.split('\n\n## 完整提示词原文\n\n', 1)[1]
    assert request['referenced_image_paths'] == [str((root/'product.png').resolve())]
    (root/'prompts/tampered.md').write_text(text.replace('不猜写、不删除、不涂平', '保留品牌即可'), encoding='utf-8')
    bad = subprocess.run([sys.executable, str(reader), str(root/'prompts/tampered.md')], capture_output=True)
    assert bad.returncode != 0
    missing = copy.deepcopy(spec); del missing['identity']['fields']['text_regions']
    run(missing, 'bad.md', False); assert not (root/'bad.md').exists()
    missing_ref = copy.deepcopy(spec); missing_ref['references'] = []
    run(missing_ref, 'bad-ref.md', False)
    unknown = copy.deepcopy(spec); unknown['identity']['fields']['accessories']['status'] = 'not_visible'; unknown['identity']['fields']['accessories']['description'] = ''
    run(unknown, 'bad-reason.md', False)
    run(spec, 'prompts/main01.md', False)
    repair = copy.deepcopy(spec); repair['stage'] = 'repair'
    run(repair, 'bad-repair.md', False)
    repair['references'].append({'path': 'product.png', 'role': 'edit_target'})
    run(repair, 'repair01.md')
    Image.new('RGB', (20, 20), 'red').save(root/'product.png')
    changed = subprocess.run([sys.executable, str(reader), str(root/'prompts/main01.md')], capture_output=True)
    assert changed.returncode != 0
print('PASS: fixed preservation text, deterministic assembly, required fields/evidence, unknown-field reasons, repair target and immutable prompt snapshots.')
