import json
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
for name in ['poster-style-transfer', 'ecommerce-visual-copywriting']:
    assert (root/'bundled'/name/'LICENSE').is_file()
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
version = (root/'VERSION').read_text(encoding='utf-8').strip()
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
