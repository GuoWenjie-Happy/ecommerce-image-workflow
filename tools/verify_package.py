import json
import hashlib
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
skill = (root / 'SKILL.md').read_text(encoding='utf-8-sig')
assert skill.startswith('---\n')
header = skill.split('---', 2)[1]
fields = dict(line.split(': ', 1) for line in header.strip().splitlines())
assert fields['name'] == root.name
assert re.fullmatch('[a-z0-9-]{1,64}', fields['name'])
assert 0 < len(fields['description']) < 1024
for path in [root/'SKILL.md', * (root/'references').glob('*.md')]:
    content = path.read_text(encoding='utf-8-sig')
    assert 'D:\\ChatGPT' not in content and 'C:\\Users\\Administrator' not in content
    for target in re.findall(r'\]\(([^)]+)\)', content):
        if not target.startswith(('http:', 'https:', '#')):
            assert (path.parent/target.split('#')[0]).is_file(), (path, target)
for name in ['poster-style-transfer', 'ecommerce-visual-copywriting', 'ecommerce-image-skills']:
    assert (root/'bundled'/name/'LICENSE').is_file()
upstream_manifest = json.loads((root/'references'/'ecommerce-image-skills-source.json').read_text(encoding='utf-8'))
upstream_root = root/'bundled'/'ecommerce-image-skills'
assert re.fullmatch(r'[0-9a-f]{40}', upstream_manifest['commit'])
upstream_files = {p.relative_to(upstream_root).as_posix(): p for p in upstream_root.rglob('*') if p.is_file()}
assert not any('.git' in Path(name).parts for name in upstream_files), 'Nested Git metadata'
assert set(upstream_files) == set(upstream_manifest['files_sha256']), 'Upstream file inventory changed'
for name, expected_hash in upstream_manifest['files_sha256'].items():
    assert hashlib.sha256(upstream_files[name].read_bytes()).hexdigest() == expected_hash, name
assert len(list((upstream_root/'skills').glob('*/SKILL.md'))) == 12
for name in ('SKILL.md', 'scripts/check_main_image.py', 'scripts/generate.py', 'scripts/online_link.py'):
    assert (upstream_root/'skills'/'amazon-white-background'/name).is_file(), name
script = root/'scripts'/'ecom_files.py'
def run(*args, ok=True):
    result = subprocess.run([sys.executable, str(script), *map(str,args)], capture_output=True, encoding='utf-8')
    assert (result.returncode == 0) == ok, (args,result.stdout,result.stderr)
    return result
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    src = base/'source'; src.mkdir()
    Image.new('RGB',(120,120),'white').save(src/'01.png')
    Image.new('RGBA',(90,160),(255,0,0,128)).save(src/'02.png')
    run('inspect',src,'--report',base/'inspect.json')
    json.loads((base/'inspect.json').read_text(encoding='utf-8'))
    run('export',src/'01.png',base/'square.png','--width',1000,'--square')
    assert Image.open(base/'square.png').size==(1000,1000)
    run('export',src/'02.png',base/'detail.png','--width',900)
    assert Image.open(base/'detail.png').size==(900,1600)
    run('export',src/'02.png',base/'bad.png','--width',1000,'--square',ok=False)
    run('export',src/'01.png',base/'square.png','--width',1000,ok=False)
    run('preview','main',src,base/'main.jpg','--width',100)
    run('preview','detail',src,base/'detail.jpg','--width',90)
    assert Image.open(base/'detail.jpg').size==(90,250)
    run('count',src,src,'--report',base/'counts.json')
    json.loads((base/'counts.json').read_text(encoding='utf-8'))
    # 模板指纹与 slots 结构校验（满长看图自检仍由人工）
    fp = json.loads(run('fingerprint', src/'01.png').stdout)
    assert re.fullmatch(r'[0-9a-f]{64}', fp['sha256'])
    # 不透明图作壳应失败；带透明内容区应通过
    run('validate-shell', src/'01.png', ok=False)
    clear = Image.new('RGBA', (120, 120), (0, 0, 0, 0))
    # 顶底栏不透明，中间透明
    for y in range(120):
        for x in range(120):
            if y < 14 or y >= 100:
                clear.putpixel((x, y), (0, 180, 0, 255))
    clear.save(base/'shell-ok.png')
    ok_shell = json.loads(run(
        'validate-shell', base/'shell-ok.png',
        '--safe-area', '0.12,0.16,0.02,0.02').stdout)
    assert ok_shell['ok'] is True and ok_shell['shell_alpha'] == 'ok'
    slots = {'canvas': [120, 120], 'separators': [
        {'between': ['a', 'b'], 'char': '|'}], 'slots': [
        {'id': 'a', 'box': [10, 90, 50, 115], 'max_chars': 4, 'font_size': 18,
         'font_weight': 'bold'},
        {'id': 'b', 'box': [70, 90, 110, 115], 'max_chars': 4, 'font_scale': 0.78,
         'font_weight': 'bold'}]}
    slots_path = base/'slots.json'
    slots_path.write_text(json.dumps(slots), encoding='utf-8')
    ok_slots = json.loads(run('validate-slots', slots_path, '--shell', src/'01.png').stdout)
    assert ok_slots['ok'] is True and ok_slots['shell']['sha256'] == fp['sha256']
    Image.new('RGBA', (120, 120), (0, 0, 0, 0)).save(base/'frame.png')
    texts = base/'texts.json'
    texts.write_text(json.dumps({'a': '测测', 'b': '试试'}), encoding='utf-8')
    framed = json.loads(run('composite-frame', src/'01.png', base/'frame.png',
                            base/'framed.png', '--slots', slots_path,
                            '--texts', texts).stdout)
    assert framed['separators_drawn'] == 1 and framed['slots_filled'] == ['a', 'b']
    bad = {'canvas': [120, 120], 'slots': [
        {'id': 'top', 'box': [10, 10, 200, 40], 'max_chars': 8}]}
    bad_path = base/'slots-bad.json'
    bad_path.write_text(json.dumps(bad), encoding='utf-8')
    run('validate-slots', bad_path, '--shell', src/'01.png', ok=False)
    # 单行拼句：compose 与 separators 不得并存；max_chars 须够拼满
    line = {'canvas': [120, 120], 'separators': [], 'selling_point_compose': {
        'slot_id': 'sp_line', 'parts': 3, 'part_max_chars': 5, 'joiner': '｜'},
        'slots': [{'id': 'sp_line', 'box': [5, 90, 115, 115], 'max_chars': 17,
                   'font_size': 18, 'font_weight': 'bold'}]}
    line_path = base/'slots-line.json'
    line_path.write_text(json.dumps(line, ensure_ascii=False), encoding='utf-8')
    assert json.loads(run('validate-slots', line_path).stdout)['ok'] is True
    mixed = dict(line)
    mixed['separators'] = [{'between': ['sp_line', 'sp_line'], 'char': '|'}]
    mixed_path = base/'slots-mixed.json'
    mixed_path.write_text(json.dumps(mixed, ensure_ascii=False), encoding='utf-8')
    run('validate-slots', mixed_path, ok=False)
version = (root/'VERSION').read_text(encoding='utf-8').strip()
project_checks = subprocess.run([sys.executable, str(root/'tools'/'test_project_files.py')], capture_output=True, encoding='utf-8')
assert project_checks.returncode == 0, (project_checks.stdout, project_checks.stderr)
print(project_checks.stdout.strip())
reference_checks = subprocess.run([sys.executable, str(root/'tools'/'test_reference_cache.py')], capture_output=True, encoding='utf-8')
assert reference_checks.returncode == 0, (reference_checks.stdout, reference_checks.stderr)
print(reference_checks.stdout.strip())
catalog_checks = subprocess.run([sys.executable, str(root/'tools'/'test_reference_catalog.py')], capture_output=True, encoding='utf-8')
assert catalog_checks.returncode == 0, (catalog_checks.stdout, catalog_checks.stderr)
print(catalog_checks.stdout.strip())
index_checks = subprocess.run([sys.executable, str(root/'tools'/'test_index_paths.py')], capture_output=True, encoding='utf-8')
assert index_checks.returncode == 0, (index_checks.stdout, index_checks.stderr)
print(index_checks.stdout.strip())
prompt_checks = subprocess.run([sys.executable, str(root/'tools'/'test_prompt_builder.py')], capture_output=True, encoding='utf-8')
assert prompt_checks.returncode == 0, (prompt_checks.stdout, prompt_checks.stderr)
print(prompt_checks.stdout.strip())
policy_checks = subprocess.run([sys.executable, str(root/'tools'/'test_repository_policy.py')], capture_output=True, encoding='utf-8')
assert policy_checks.returncode == 0, (policy_checks.stdout, policy_checks.stderr)
print(policy_checks.stdout.strip())
assert re.fullmatch(r'\d+\.\d+\.\d+', version), 'Invalid VERSION'
if '--build' not in sys.argv:
    print('PASS: metadata, internal links, portable paths, licenses and file operation checks.')
    sys.exit(0)
out = root/'dist'/f'ecommerce-image-workflow-{version}.zip'
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
    included = [root/name for name in ('SKILL.md','README.md','VERSION')]
    for folder in ('agents','references','scripts','bundled'):
        included.extend((root/folder).rglob('*'))
    for path in sorted(included):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            archive.write(path, 'ecommerce-image-workflow/'+path.relative_to(root).as_posix())
with zipfile.ZipFile(out) as archive:
    assert archive.testzip() is None
    assert all(n.startswith('ecommerce-image-workflow/') for n in archive.namelist())
print('PASS: entry metadata, internal reference links, portable paths, licenses, inspect, exports, ratio/overwrite guards, previews, counts and ZIP integrity.')
print('NOTE: this script does not run official quick_validate or exercise image generation.')
print(out)
