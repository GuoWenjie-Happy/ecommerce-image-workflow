"""Batch reference metadata and reusable contact sheets; never analyzes designs."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import tempfile
from PIL import Image
import ecom_files
from project_files import atomic, digest, encode, lock, now, read_json


def fingerprint(data):
    return hashlib.sha256(encode(data)).hexdigest()


def relative_location(path, base):
    """Keep portable links when possible; cross-drive overrides stay explicit."""
    try:
        return Path(os.path.relpath(path, base)).as_posix(), False
    except ValueError:
        return str(path), True


def validate_legacy_relocation(index, root):
    """Only adopt a relocated legacy cache when all recorded sources still match."""
    count = 0
    for record in index.get('categories', {}).values():
        files = record.get('files', [])
        if not files or record.get('fingerprint') != fingerprint({'files': files, 'contact_sheet_version': 1}):
            raise ValueError('Legacy relocation needs a valid source inventory')
        for entry in files:
            value = entry['path']
            relative = Path(value.replace('\\', '/'))
            path = (root/relative).resolve()
            if relative.is_absolute() or PureWindowsPath(value).is_absolute() or not path.is_relative_to(root) or not path.is_file() or digest(path) != entry['sha256']:
                raise ValueError('Legacy relocation source differs or is missing; verify suite mapping before migration')
            count += 1
    if not count:
        raise ValueError('Cannot relocate empty legacy cache')


def changes(before, after):
    old = {entry['path']: entry for entry in before}
    new = {entry['path']: entry for entry in after}
    return {
        'added': [path for path in new if path not in old],
        'removed': [path for path in old if path not in new],
        'modified': [path for path in new if path in old and new[path] != old[path]],
        'unchanged': [path for path in new if path in old and new[path] == old[path]],
        'sequence_changed': list(old) != list(new),
    }


def analysis_state(analysis, previous, files, token, rules):
    valid = bool(analysis.get('analysis')) and analysis.get('rules_version') == rules
    current = valid and analysis.get('source_fingerprint') == token
    basis = None
    if current:
        basis = {'fingerprint': token, 'files': files}
    elif valid:
        saved = previous.get('analysis_basis') or {}
        if saved.get('fingerprint') == analysis.get('source_fingerprint'):
            basis = saved
        elif previous.get('fingerprint') == analysis.get('source_fingerprint'):
            basis = {'fingerprint': previous['fingerprint'], 'files': previous['files']}
    return {
        'analysis_required': not current,
        'analysis_scope': 'none' if current else ('incremental' if basis else 'full'),
        'analysis_basis': basis,
        'analysis_changes': changes(basis['files'] if basis else [], files),
    }


def prepare(spec):
    root = Path(spec['root']).resolve(strict=True)
    categories = spec['categories']
    if not root.is_dir() or not isinstance(categories, dict) or not categories or not set(categories) <= {'main', 'detail'}:
        raise ValueError('Expected suite directory and explicit main/detail categories')
    default_cache = (root/'_参考缓存').resolve()
    cache = Path(spec.get('cache', default_cache)).resolve()
    location_reason = None
    if cache != default_cache:
        location_reason = spec.get('cache_override')
        if not isinstance(location_reason, dict) or location_reason.get('kind') not in {'write_error', 'permission_restriction', 'user_request'} or not isinstance(location_reason.get('evidence'), str) or not location_reason['evidence'].strip():
            raise ValueError('Nondefault cache requires cache_override kind and concrete evidence; use the suite _参考缓存 by default')
    if cache == root:
        raise ValueError('Cache must be a dedicated derived-output directory')
    folders = {}
    for kind, relative in categories.items():
        folder = (root/relative).resolve(strict=True)
        if not folder.is_dir() or not folder.is_relative_to(root):
            raise ValueError('Reference category must be inside the suite')
        if cache == folder or folder.is_relative_to(cache):
            raise ValueError('Cache cannot contain or replace source category')
        folders[kind] = folder
    index_path = cache/'index.json'
    with lock(index_path):
        if index_path.exists():
            index = read_json(index_path)
            version = index.get('schema_version')
            if version == 1:
                if index.get('source') != str(root):
                    validate_legacy_relocation(index, root)
            elif version == 2 and index.get('source_base') == 'cache_directory':
                source = index['source']
                if not index.get('source_external') and (Path(source).is_absolute() or PureWindowsPath(source).is_absolute()):
                    raise ValueError('Relative cache source cannot be absolute')
                if (cache/source).resolve() != root:
                    raise ValueError('Cache belongs to another source')
            else:
                raise ValueError('Cache belongs to another source or schema')
        else:
            if any((cache/name).exists() for name in ('main_overview.jpg', 'detail_overview.jpg')):
                raise ValueError('Unregistered preview files exist; refusing to overwrite')
            index = {'categories': {}}
        results = {}
        for kind, folder in folders.items():
            paths = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ecom_files.EXTENSIONS and not p.is_relative_to(cache)), key=ecom_files.natural)
            if not paths:
                raise ValueError(f'No reference images: {folder}')
            files = []
            for path in paths:
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    raise ValueError('Reference symlink escapes suite')
                with Image.open(path) as image:
                    image.load()
                    files.append({'path': path.relative_to(root).as_posix(), 'id': path.stem, 'width': image.width, 'height': image.height, 'ratio': image.width/image.height, 'sha256': digest(path)})
            token = fingerprint({'files': files, 'contact_sheet_version': 1})
            previous = index['categories'].get(kind, {})
            filename = kind+'_overview.jpg'
            preview = cache/filename
            updated = previous.get('fingerprint') != token or not preview.is_file() or previous.get('preview_sha256') != digest(preview)
            if updated:
                fd, temporary = tempfile.mkstemp(dir=cache, prefix=kind+'_', suffix='.jpg')
                os.close(fd)
                os.unlink(temporary)  # ecom_files refuses existing outputs.
                try:
                    ecom_files.preview(argparse.Namespace(files=paths, input=str(folder), output=temporary, kind='main', width=300, columns=4))
                    os.replace(temporary, preview)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            analysis_file = cache/(kind+'_analysis.json')
            analysis = {}
            if analysis_file.is_file():
                try:
                    analysis = read_json(analysis_file)
                except (OSError, ValueError):
                    pass
            rules = spec.get('analysis_rules_version', '1')
            ids = [entry['id'] for entry in files]
            record = {'fingerprint': token, 'files': files, 'duplicate_ids': sorted({key for key in ids if ids.count(key) > 1}), 'preview': filename, 'preview_sha256': digest(preview), 'changes': changes(previous.get('files', []), files), 'analysis_rules_version': rules,
                      **analysis_state(analysis, previous, files, token, rules)}
            index['categories'][kind] = record
            results[kind] = {**record, 'updated': updated}
        source, source_external = relative_location(root, cache)
        actual, actual_external = relative_location(cache, root)
        index.update(schema_version=2, source=source, source_base='cache_directory', source_external=source_external)
        index['cache_location'] = {'path_base': 'suite', 'default': '_参考缓存', 'actual': actual,
                                   'actual_external': actual_external, 'override': location_reason}
        index['checked_at'] = now()
        atomic(index_path, encode(index))
    return {'source': str(root), 'cache': str(cache), 'cache_location': index['cache_location'], 'status': 'completed', 'categories': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    request = read_json(args.manifest)
    sets = request['sets']
    if not isinstance(sets, list) or not sets:
        raise ValueError('Expected nonempty sets list')
    for spec in sets:
        try:
            # Contact sheet helper prints a report; preserve single JSON result per set.
            from contextlib import redirect_stdout
            import io
            with redirect_stdout(io.StringIO()):
                result = prepare(spec)
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            print(json.dumps({'source': spec.get('root'), 'status': 'failed', 'error': str(exc)}, ensure_ascii=False))
            return 1
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
