"""Audit or explicitly rebase selected JSON path fields; never rewrites history."""
import argparse
import copy
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
from project_files import atomic, digest, encode, lock, read_json


def foreign_path(value):
    return PureWindowsPath(value) if PureWindowsPath(value).drive or '\\' in value else PurePosixPath(value)


def remap(value, mappings):
    path = foreign_path(value)
    matches = []
    for entry in mappings:
        old = foreign_path(entry['from'])
        if not old.is_absolute() or not Path(entry['to']).is_absolute():
            raise ValueError('Mappings require explicit absolute old and current roots')
        try:
            suffix = path.relative_to(old)
        except ValueError:
            continue
        target_root = Path(entry['to']).resolve(strict=True)
        if not target_root.is_dir():
            raise ValueError('Mapping target must be a directory')
        resolved = target_root.joinpath(*suffix.parts).resolve()
        if not resolved.is_relative_to(target_root):
            raise ValueError('Mapped path escapes registered root')
        matches.append((len(old.parts), resolved))
    if not matches:
        return Path(value)
    longest = max(length for length, _ in matches)
    winners = {p for length, p in matches if length == longest}
    if len(winners) != 1:
        raise ValueError('Ambiguous path mapping')
    return winners.pop()


def pointer_parent(document, pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('Expected explicit JSON pointer')
    parts = [part.replace('~1', '/').replace('~0', '~') for part in pointer[1:].split('/')]
    node = document
    for key in parts[:-1]:
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node, int(parts[-1]) if isinstance(node, list) else parts[-1]


def process(request):
    """All documents preflight before any write; apply is opt-in with stale guards."""
    jobs, results, seen = [], [], set()
    for spec in request['documents']:
        base = Path(spec['base']).resolve(strict=True)
        path = (base/spec['file']).resolve(strict=True)
        if not base.is_dir() or not path.is_relative_to(base) or path.suffix != '.json' or path in seen:
            raise ValueError('Each index must be a unique JSON file inside its declared base')
        seen.add(path)
        original = read_json(path)
        data = copy.deepcopy(original)
        before = digest(path)
        rows, pointers = [], set()
        for field in spec['fields']:
            pointer = field['pointer']
            if pointer in pointers:
                raise ValueError('Duplicate field pointer')
            pointers.add(pointer)
            node, key = pointer_parent(data, pointer)
            value = node[key]
            if not isinstance(value, str) or not value:
                raise ValueError('Selected path field must be a nonempty string')
            mapped = remap(value, request.get('mappings', []))
            if foreign_path(value).is_absolute() and not mapped.is_absolute():
                raise ValueError('Foreign absolute path needs an explicit mapping')
            resolved = (base/mapped).resolve(strict=True)
            inside = resolved.is_relative_to(base)
            if not inside and not field.get('external', False):
                raise ValueError('External dependency must be explicitly declared')
            if isinstance(node, dict) and key in ('path', 'file') and node.get('sha256'):
                if not resolved.is_file() or digest(resolved) != node['sha256']:
                    raise ValueError('Mapped evidence hash differs')
            node[key] = resolved.relative_to(base).as_posix() if inside else str(resolved)
            rows.append({'pointer': pointer, 'value': node[key], 'external': not inside})
        jobs.append((path, data, before))
        results.append({'file': str(path), 'changed': data != original, 'fields': rows})
    if request.get('apply') is True:
        for path, data, before in jobs:
            with lock(path):
                if digest(path) != before:
                    raise ValueError('Index changed since preflight; reload before migration')
                atomic(path, encode(data))
    return {'applied': request.get('apply') is True, 'documents': results}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(process(read_json(args.manifest)), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
