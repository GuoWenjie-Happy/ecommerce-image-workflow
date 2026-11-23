"""Explicit migrations for project/product/template indexes with preflight guards."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from index_paths import process, remap
from project_files import digest

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base/'input').mkdir()
    (base/'input/a.txt').write_text('evidence', encoding='utf-8')
    document = base/'project.json'
    document.write_text(json.dumps({'inputs': {'products': '/old/project/input'},
                                    'note': '/old/project is historical text'}), encoding='utf-8')
    request = {'mappings': [{'from': '/old/project', 'to': str(base)}],
               'documents': [{'base': str(base), 'file': 'project.json',
                              'fields': [{'pointer': '/inputs/products'}]}]}
    before = document.read_bytes()
    report = process(request)
    assert not report['applied'] and document.read_bytes() == before
    assert report['documents'][0]['fields'][0]['value'] == 'input'
    # Invalid later documents must not leave earlier documents partially migrated.
    invalid = {**request, 'apply': True, 'documents': request['documents'] + [
        {'base': str(base), 'file': 'missing.json', 'fields': []}]}
    try:
        process(invalid)
        raise AssertionError('Missing file accepted')
    except FileNotFoundError:
        pass
    assert document.read_bytes() == before
    process({**request, 'apply': True})
    data = json.loads(document.read_text(encoding='utf-8'))
    assert data['inputs']['products'] == 'input' and data['note'] == '/old/project is historical text'
    relative = base/'relative.json'
    relative.write_text(json.dumps({'path': 'input/a.txt'}), encoding='utf-8')
    process({**request, 'apply': True, 'documents': [{'base': str(base), 'file': 'relative.json',
              'fields': [{'pointer': '/path', 'from_base': '/old/project'}]}]})
    assert json.loads(relative.read_text(encoding='utf-8'))['path'] == 'input/a.txt'
    external = base/'external.json'
    external.write_text(json.dumps({'path': str(base.parent)}), encoding='utf-8')
    try:
        process({'documents': [{'base': str(base), 'file': 'external.json', 'fields': [{'pointer': '/path'}]}]})
        raise AssertionError('Undeclared external dependency accepted')
    except ValueError as exc:
        assert 'External dependency' in str(exc)
    # Windows root migration is recognized regardless of current OS.
    assert remap('C:\\old\\project\\input\\a.txt', [{'from': 'C:\\old\\project', 'to': str(base)}]) == base/'input/a.txt'
    template = base/'template.json'
    template.write_text(json.dumps({'shell': {'path': '/old/project/input/a.txt', 'sha256': '0'*64}}), encoding='utf-8')
    bad_hash = {**request, 'apply': True, 'documents': [{'base': str(base), 'file': 'template.json', 'fields': [{'pointer': '/shell/path'}]}]}
    try:
        process(bad_hash)
        raise AssertionError('Changed evidence accepted')
    except ValueError as exc:
        assert 'hash differs' in str(exc)
    data = json.loads(template.read_text(encoding='utf-8'))
    data['shell']['sha256'] = digest(base/'input/a.txt')
    template.write_text(json.dumps(data), encoding='utf-8')
    process(bad_hash)
    assert json.loads(template.read_text(encoding='utf-8'))['shell']['path'] == 'input/a.txt'
print('PASS: explicit field migration, dry-run, cross-OS mappings, hash checks and preflight failure without writes.')
