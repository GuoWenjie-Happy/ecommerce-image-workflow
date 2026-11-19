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
    body = text.split('\n\n## 完整提示词原文\n\n', 1)[1]
    assert '商品核对' in body and '不猜写' in body
    assert '包装与本体文字' in body
    assert '须按附图原样保留' not in body  # 短版：硬要求不逐条重复
    assert 'shape_proportions' not in body  # 默认不把英文字段名塞进生图串
    assert '商品保真固定条款' not in body  # 默认不贴保真全文
    assert json.loads(a.stdout)['result']['prompt_mode'] == 'identity_brief'
    b = run(spec, 'prompts/main02.md')
    assert json.loads(a.stdout)['result']['prompt_sha256'] == json.loads(b.stdout)['result']['prompt_sha256']
    reader = script.parent/'prompt_builder.py'
    read = subprocess.run([sys.executable, str(reader), str(root/'prompts/main01.md')], capture_output=True, encoding='utf-8')
    assert read.returncode == 0, read.stderr
    request = json.loads(read.stdout)
    assert request['prompt'] == body
    assert request['referenced_image_paths'] == [str((root/'product.png').resolve())]
    (root/'prompts/tampered.md').write_text(text.replace('不猜写', '可以猜写'), encoding='utf-8')
    bad = subprocess.run([sys.executable, str(reader), str(root/'prompts/tampered.md')], capture_output=True)
    assert bad.returncode != 0
    # 归档开关：可恢复「整表观察+保真全文」入提示词
    legacy = copy.deepcopy(spec)
    legacy['full_legacy_preservation_prompt'] = True
    run(legacy, 'prompts/main-legacy.md')
    legacy_body = (root/'prompts/main-legacy.md').read_text(encoding='utf-8').split(
        '\n\n## 完整提示词原文\n\n', 1)[1]
    assert '商品保真固定条款' in legacy_body and 'shape_proportions' in legacy_body
    assert '商品核对' not in legacy_body  # 短版块未混入
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
    # 密文页：缺说明不得 compose；完整 copy_units 须写入提示词
    dense = copy.deepcopy(spec)
    dense['stage'] = 'detail'
    dense['output_spec'] = '900×1600px'
    dense['dense_copy'] = True
    run(dense, 'bad-dense.md', False)
    dense['copy_units'] = [
        {'id': 'L1', 'title': '不够甜香', 'body': ''},
        {'id': 'R1', 'title': '红颜香甜', 'body': '红颜品种，甜香带酸'}]
    run(dense, 'bad-dense-body.md', False)
    dense['copy_units'][0]['body'] = '担心不够甜不够香'
    dense['copy'] = '不够甜香｜担心口感寡淡。大小混装｜担心大果小果。'
    ok_dense = run(dense, 'prompts/detail02.md')
    dense_text = (root/'prompts/detail02.md').read_text(encoding='utf-8')
    assert '担心不够甜不够香' in dense_text and '禁止自撰' in dense_text
    assert '见下方分位' in dense_text
    assert '上图文字分位' in dense_text
    assert '担心口感寡淡' not in dense_text  # 有分位则不双写摘要
    assert json.loads(ok_dense.stdout)['result']['prompt_sha256']
    # 成图禁词与套框/对照/多窗硬闸
    banned = copy.deepcopy(spec)
    banned['copy'] = '资料来源：http://example.com'
    run(banned, 'bad-source.md', False)
    banned['copy'] = '产品保真2300m产地'
    run(banned, 'bad-fidelity.md', False)
    framed = copy.deepcopy(spec)
    framed['uses_brand_frame'] = True
    run(framed, 'bad-frame.md', False)
    framed['safe_area'] = {'top': 0.12, 'bottom': 0.16, 'left': 0.02, 'right': 0.02}
    run(framed, 'prompts/main-framed.md')
    scale = copy.deepcopy(spec)
    scale['physical_scale'] = True
    run(scale, 'bad-scale.md', False)
    scale['scale_alignment'] = '果与尺共面，刻度朝读者'
    scale['layout'] = '果与尺共面对照，刻度朝读者'
    run(scale, 'prompts/main-scale.md')
    # 未开对照却点名尺币 → 失败
    coin = copy.deepcopy(spec)
    coin['layout'] = '上排用硬币或直尺对照中大果'
    run(coin, 'bad-coin.md', False)
    icons = copy.deepcopy(spec)
    icons['icon_list'] = True
    run(icons, 'bad-icons.md', False)
    icons['icon_uniform'] = True
    run(icons, 'prompts/main-icons.md')
    panels = copy.deepcopy(spec)
    panels['multi_panel'] = True
    run(panels, 'bad-panels.md', False)
    panels['panel_count'] = 2
    run(panels, 'prompts/main-panels.md')
print('PASS: fixed preservation text, deterministic assembly, required fields/evidence, unknown-field reasons, repair target and immutable prompt snapshots.')
