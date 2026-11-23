"""Ensure mandatory preservation instructions survive prompt assembly."""
import copy
import json
import shutil
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
    assert '商品核对' in body and '商品以 product 附图为唯一形态依据' in body
    assert '包装与本体文字' in body
    assert '须按附图原样保留' not in body  # 短版：硬要求不逐条重复
    assert 'shape_proportions' not in body  # 默认不把英文字段名塞进生图串
    assert '商品保真固定条款' not in body  # 默认不贴保真全文
    # 默认生图串只描述目标画面；内部限制和通用禁止句不进入提示词。
    assert '本张限制' not in body and '不增加道具' not in body
    assert all(marker not in body for marker in (
        '禁止', '不得', '不要', '不猜写', '不新增', '不补看不见'))
    assert '画面文字完整范围' in body
    assert json.loads(a.stdout)['result']['prompt_mode'] == 'identity_brief'
    b = run(spec, 'prompts/main02.md')
    assert json.loads(a.stdout)['result']['prompt_sha256'] == json.loads(b.stdout)['result']['prompt_sha256']
    reader = script.parent/'prompt_builder.py'
    read = subprocess.run([sys.executable, str(reader), str(root/'prompts/main01.md')], capture_output=True, encoding='utf-8')
    assert read.returncode == 0, read.stderr
    request = json.loads(read.stdout)
    assert request['prompt'] == body
    assert request['referenced_image_paths'] == [str((root/'product.png').resolve())]
    # Relocation never edits the archived request, and still verifies image bytes.
    with tempfile.TemporaryDirectory() as moved_tmp:
        moved = Path(moved_tmp)/'project'
        shutil.copytree(root, moved)
        from_path = str(root/'prompts/main01.md')
        sys.path.insert(0, str(script.parent))
        from prompt_builder import load_request
        snapshot = moved/'prompts/main01.md'
        before = snapshot.read_bytes()
        portable = load_request(snapshot, project_root=moved)
        assert portable['referenced_image_paths'] == [str((moved/'product.png').resolve())]
        assert portable['prompt'] == body and snapshot.read_bytes() == before
        legacy_metadata, legacy_body = text.split('\n\n## 完整提示词原文\n\n', 1)
        prefix, metadata_json = legacy_metadata.split('组装依据及真实参数：\n', 1)
        metadata = json.loads(metadata_json)
        for item in metadata['source_evidence'] + metadata['reference_evidence']:
            item.pop('project_path', None)
        legacy_snapshot = moved/'prompts/legacy-paths.md'
        legacy_snapshot.write_text(prefix+'组装依据及真实参数：\n'+json.dumps(metadata)+'\n\n## 完整提示词原文\n\n'+legacy_body, encoding='utf-8')
        mapped = load_request(legacy_snapshot, path_mappings=[{'from': str(root), 'to': str(moved)}])
        assert mapped['referenced_image_paths'] == portable['referenced_image_paths']
        Image.new('RGB', (20, 20), 'blue').save(moved/'product.png')
        try:
            load_request(snapshot, project_root=moved)
            raise AssertionError('Changed moved evidence accepted')
        except ValueError as exc:
            assert 'evidence changed' in str(exc)
        assert snapshot.read_bytes() == before
    (root/'prompts/tampered.md').write_text(
        text.replace('唯一形态依据', '可选形态依据'), encoding='utf-8')
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
    assert '担心不够甜不够香' in dense_text and '画面文字范围' in dense_text
    assert '见下方分位' in dense_text
    assert '画面文字分位' in dense_text
    assert '担心口感寡淡' not in dense_text  # 有分位则不双写摘要
    assert json.loads(ok_dense.stdout)['result']['prompt_sha256']
    # 成图禁词与套框/对照/多窗硬闸
    banned = copy.deepcopy(spec)
    banned['copy'] = '资料来源：http://example.com'
    run(banned, 'bad-source.md', False)
    banned['copy'] = '产品保真2300m产地'
    run(banned, 'bad-fidelity.md', False)
    negative_style = copy.deepcopy(spec)
    negative_style['style'] = '浅色背景，禁止使用蓝色'
    run(negative_style, 'bad-negative-style.md', False)
    negative_layout = copy.deepcopy(spec)
    negative_layout['layout'] = '完整商品居中，不要纸箱'
    run(negative_layout, 'bad-negative-layout.md', False)
    negative_output = copy.deepcopy(spec)
    negative_output['output_spec'] = '1000×1000px，禁止裁切'
    run(negative_output, 'bad-negative-output.md', False)
    negative_identity = copy.deepcopy(spec)
    negative_identity['identity']['fields']['structure']['description'] = '不要增加纸箱'
    run(negative_identity, 'bad-negative-identity.md', False)
    absent = copy.deepcopy(spec)
    absent['product_visible'] = False
    absent['absence_reason'] = '内部素材缺口：没有包装实拍'
    absent['layout'] = '三张信息卡组成的箱装发货示意页'
    run(absent, 'prompts/main-absent.md')
    absent_text = (root/'prompts/main-absent.md').read_text(encoding='utf-8')
    assert '内部素材缺口' not in absent_text and '没有包装实拍' not in absent_text
    assert '商品出镜：否。' in absent_text
    internal = copy.deepcopy(spec)
    internal['internal_notes'] = '资料仅支持产区名称，没有真章图资产。'
    run(internal, 'prompts/main-internal-notes.md')
    internal_text = (root/'prompts/main-internal-notes.md').read_text(encoding='utf-8')
    assert '没有真章图资产' not in internal_text
    for i, process_copy in enumerate((
            '地理标志产区名称可成立表述，无章图贴图',
            '文案可写产区名称，画面禁止仿官方章',
            '无包装实拍，以线框图示意')):
        leaked = copy.deepcopy(spec)
        leaked['copy'] = process_copy
        run(leaked, f'bad-process-copy-{i}.md', False)
    leaked_unit = copy.deepcopy(spec)
    leaked_unit['copy_units'] = [{
        'id': 'A1', 'title': '箱装发货', 'body': '无包装实拍，以线框图示意'}]
    run(leaked_unit, 'bad-process-copy-unit.md', False)
    # 产品级插画系统：页面只能继承已锁定的 style_id。
    illustrated = copy.deepcopy(spec)
    illustrated['identity']['illustration_system'] = {
        'scope': 'product',
        'style_id': 'flat_sticker',
        'style_source': 'detail/11',
        'palette': '红、米白、深色描边',
        'outline': '统一粗描边和圆角图标',
        'shading': '少量平涂阴影',
        'shared_shell': '示意页共享信息卡外壳'}
    illustrated['illustration_style_id'] = 'flat_sticker'
    run(illustrated, 'prompts/detail-illustrated.md')
    illustrated_text = (root/'prompts/detail-illustrated.md').read_text(encoding='utf-8')
    assert '产品级插画系统' in illustrated_text and 'flat_sticker' in illustrated_text
    mismatched = copy.deepcopy(illustrated)
    mismatched['illustration_style_id'] = 'engineering_line'
    run(mismatched, 'bad-illustration-style.md', False)
    negative_illustration = copy.deepcopy(illustrated)
    negative_illustration['identity']['illustration_system']['shading'] = '禁止纪实光影'
    run(negative_illustration, 'bad-negative-illustration.md', False)
    missing_system = copy.deepcopy(spec)
    missing_system['illustration_style_id'] = 'flat_sticker'
    run(missing_system, 'bad-illustration-system.md', False)
    # 结构化区域替代自由 layout，不得重复准确文案。
    regions = copy.deepcopy(spec)
    regions['layout'] = '这段旧的模糊构图不应进入提示词'
    regions['layout_regions'] = [
        {'role': 'title_area', 'position': 'top', 'height': '25%',
         'background': '浅色场景，轻微暗化', 'content_role': '主标题与副标题'},
        {'role': 'hero', 'position': 'center_lower', 'content_role': '商品主体'}]
    run(regions, 'prompts/main-regions.md')
    regions_text = (root/'prompts/main-regions.md').read_text(encoding='utf-8')
    assert '结构化构图区域' in regions_text
    assert '这段旧的模糊构图不应进入提示词' not in regions_text
    duplicate_role = copy.deepcopy(regions)
    duplicate_role['layout_regions'][1]['role'] = 'title_area'
    run(duplicate_role, 'bad-region-role.md', False)
    missing_region_field = copy.deepcopy(regions)
    del missing_region_field['layout_regions'][0]['content_role']
    run(missing_region_field, 'bad-region-field.md', False)
    invalid_percentage = copy.deepcopy(regions)
    invalid_percentage['layout_regions'][0]['height'] = '125%'
    run(invalid_percentage, 'bad-region-percentage.md', False)
    duplicated_copy = copy.deepcopy(regions)
    duplicated_copy['layout_regions'][0]['content_role'] = '主标题：测试文字'
    run(duplicated_copy, 'bad-region-copy.md', False)
    negative_region = copy.deepcopy(regions)
    negative_region['layout_regions'][0]['background'] = '浅色场景，禁止蓝色'
    run(negative_region, 'bad-negative-region.md', False)
    # 唯一允许的负向边界：绑定本次实际 design 参考图中的具体元素。
    Image.new('RGB', (20, 20), 'orange').save(root/'design.png')
    exclusions = copy.deepcopy(spec)
    exclusions['references'].append({'path': 'design.png', 'role': 'design'})
    exclusions['reference_exclusions'] = [{
        'reference': 'design.png',
        'elements': ['橙子', '原品牌包装']}]
    run(exclusions, 'prompts/main-reference-exclusions.md')
    exclusions_text = (root/'prompts/main-reference-exclusions.md').read_text(encoding='utf-8')
    assert '参考图使用边界' in exclusions_text
    assert '输入图2' in exclusions_text and '橙子、原品牌包装不继承' in exclusions_text
    unbound_exclusion = copy.deepcopy(spec)
    unbound_exclusion['reference_exclusions'] = [{
        'reference': 'product.png', 'elements': ['纸箱']}]
    run(unbound_exclusion, 'bad-unbound-exclusion.md', False)
    malformed_exclusion = copy.deepcopy(exclusions)
    malformed_exclusion['reference_exclusions'] = ['禁止橙子']
    run(malformed_exclusion, 'bad-malformed-exclusion.md', False)
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
