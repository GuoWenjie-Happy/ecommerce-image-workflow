"""Reusable file operations only; never generates or retouches product pixels."""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff'}


def natural(path):
    return [int(x) if x.isdigit() else x.casefold()
            for x in re.split(r'(\d+)', path.stem)]


def inputs(path):
    path = Path(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise ValueError(f'Input does not exist: {path}')
    return sorted((p for p in path.iterdir()
                   if p.is_file() and p.suffix.lower() in EXTENSIONS), key=natural)


def destination(path):
    path = Path(path)
    if path.exists():
        raise ValueError(f'Refusing to overwrite: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def report(data, path=None):
    message = json.dumps(data, ensure_ascii=False, indent=2)
    if path:
        destination(path).write_text(message, encoding='utf-8')
    print(message)


def inspect(path):
    with Image.open(path) as original:
        original.load()
        im = ImageOps.exif_transpose(original).convert('RGBA')
        alpha = im.getchannel('A')
        transparent = alpha.getextrema()[0] < 255
        # Approximation for checking backgrounds; not semantic segmentation.
        if transparent:
            bbox = alpha.getbbox()
        else:
            rgb = im.convert('RGB')
            difference = ImageChops.difference(rgb, Image.new('RGB', im.size, 'white'))
            mask = difference.point(lambda x: 255 if x > 12 else 0)
            channels = mask.split()
            bbox = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2]).getbbox()
        sample = im.copy()
        sample.thumbnail((512, 512))
        w, h = sample.size
        band = max(1, round(min(w, h) * .02))
        border = []
        for box in [(0, 0, w, band), (0, h-band, w, h),
                    (0, band, band, h-band), (w-band, band, w, h-band)]:
            border.extend(sample.crop(box).getdata())
        opaque = [p for p in border if p[3] == 255]
        white = sum(min(p[:3]) >= 252 for p in opaque)
        return {
            'file': str(path.resolve()), 'format': original.format,
            'width': im.width, 'height': im.height,
            'ratio_width_over_height': im.width / im.height,
            'bytes': path.stat().st_size, 'mode': original.mode,
            'has_actual_transparency': transparent,
            'alpha_range': alpha.getextrema(), 'foreground_bbox_approx': bbox,
            'foreground_long_edge_fraction_approx':
                max(bbox[2]-bbox[0], bbox[3]-bbox[1]) / max(im.size) if bbox else 0,
            'opaque_border_near_white_fraction_sampled': white / len(opaque) if opaque else None,
            'note': 'Geometric/background checks only; shadows may affect bbox. No visual approval.'
        }


def save_image(im, path):
    path = destination(path)
    if path.suffix.lower() in {'.jpg', '.jpeg'}:
        if max(im.size) >= 65500:
            raise ValueError('JPEG preview too long; choose PNG or a smaller preview width.')
        if im.mode == 'RGBA':
            flat = Image.new('RGB', im.size, 'white')
            flat.paste(im, mask=im.getchannel('A'))
            im = flat
        im.convert('RGB').save(path, quality=95, subsampling=0)
    elif path.suffix.lower() == '.png':
        im.save(path, format='PNG')
    else:
        raise ValueError('Output must be PNG or JPEG.')


def export(args):
    with Image.open(args.input) as source:
        im = ImageOps.exif_transpose(source)
        if args.square and im.width != im.height:
            raise ValueError('Non-square main image: refusing to stretch or crop.')
        native = im.size
        target = (args.width, max(1, round(im.height * args.width / im.width)))
        im = im.resize(target, Image.Resampling.LANCZOS)
        save_image(im, args.output)
        report({'source': args.input, 'output': args.output,
                'native': native, 'exported': target, 'upscaled': args.width > native[0]})


def _pingfang_ttc_paths():
    """苹果苹方：旧版 Fonts/、新版 MobileAsset（哈希目录会变，用 glob）。"""
    found = []
    assets = Path('/System/Library/AssetsV2')
    candidates = [
        Path('/System/Library/Fonts/PingFang.ttc'),
        *(assets.glob('com_apple_MobileAsset_Font*/**/AssetData/PingFang.ttc')
          if assets.is_dir() else ()),
    ]
    for path in candidates:
        if path.is_file() and path not in found:
            found.append(path)
    return found


def _cjk_font_candidates(want_bold):
    """苹果优先苹方 SC；粗体用 Semibold→Medium。其它系统再回退雅黑/Noto。"""
    # PingFang SC：Regular=3, Medium=7, Semibold=11（HK/MO/TC/SC 四语文一套）
    apple = []
    for path in _pingfang_ttc_paths():
        if want_bold:
            apple.extend([(path, 11), (path, 7), (path, 3)])
        else:
            apple.extend([(path, 3), (path, 7)])
    if want_bold:
        other = [
            (Path('C:/Windows/Fonts/msyhbd.ttc'), 0),
            (Path('C:/Windows/Fonts/simhei.ttf'), 0),
            (Path('/System/Library/Fonts/STHeiti Medium.ttc'), 0),
            (Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'), 0),
            (Path('/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc'), 0),
            (Path('C:/Windows/Fonts/msyh.ttc'), 0),
            (Path('/System/Library/Fonts/STHeiti Light.ttc'), 0),
        ]
    else:
        other = [
            (Path('C:/Windows/Fonts/msyh.ttc'), 0),
            (Path('/System/Library/Fonts/STHeiti Light.ttc'), 0),
            (Path('/Library/Fonts/Arial Unicode.ttf'), 0),
            (Path('C:/Windows/Fonts/simhei.ttf'), 0),
            (Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'), 0),
            (Path('/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'), 0),
            (Path('/System/Library/Fonts/STHeiti Medium.ttc'), 0),
        ]
    return apple + other


def _cjk_font(size, weight='bold'):
    """加载中文字体；Apple 优先苹方；bold 时优先 Semibold。"""
    want_bold = str(weight).lower() in ('bold', 'semibold', 'medium', 'heavy', 'black')
    for path, index in _cjk_font_candidates(want_bold):
        if not path.is_file():
            continue
        try:
            return ImageFont.truetype(str(path), size=size, index=index), want_bold
        except OSError:
            try:
                return ImageFont.truetype(str(path), size=size), want_bold
            except OSError:
                continue
    return ImageFont.load_default(), want_bold


def _slot_type_size(slot, height):
    """字号：font_size 优先，否则 font_scale×栏高；默认 scale=0.78（贴示意栏高，勿用过小默认）。"""
    if isinstance(slot.get('font_size'), int) and slot['font_size'] > 0:
        return slot['font_size']
    scale = slot.get('font_scale')
    if not isinstance(scale, (int, float)) or scale <= 0:
        scale = 0.78
    return max(16, int(height * float(scale)))


def _slot_font(slot, height):
    size = _slot_type_size(slot, height)
    weight = slot.get('font_weight') or 'bold'
    font, want_bold = _cjk_font(size, weight=weight)
    return font, size, want_bold


def _separator_points(sep, slots_by_id):
    """解析分隔位置：绝对坐标或两槽 box 中点。"""
    if 'x' in sep and 'y' in sep:
        return float(sep['x']), float(sep['y']), int(sep.get('font_size') or 28), sep.get('font_weight') or 'bold'
    pair = sep.get('between')
    if not (isinstance(pair, list) and len(pair) == 2):
        raise ValueError('separator 须有 x,y 或 between:[id1,id2]')
    a, b = slots_by_id.get(pair[0]), slots_by_id.get(pair[1])
    if not a or not b:
        raise ValueError(f'separator.between 找不到槽: {pair}')
    la, ta, ra, ba = a['box']
    lb, tb, rb, bb = b['box']
    x = ((ra + lb) / 2) if ra <= lb else ((la + ra + lb + rb) / 4)
    y = (min(ta, tb) + max(ba, bb)) / 2
    height = max(12, max(ba - ta, bb - tb))
    if isinstance(sep.get('font_size'), int) and sep['font_size'] > 0:
        font_size = sep['font_size']
    else:
        # 分隔符字号跟邻近槽一致：取两侧槽字号均值，否则栏高×0.78
        sizes = [_slot_type_size(a, height), _slot_type_size(b, height)]
        font_size = max(16, int(sum(sizes) / 2))
    weight = sep.get('font_weight') or a.get('font_weight') or b.get('font_weight') or 'bold'
    return x, y, font_size, weight


def composite_frame(args):
    """将RGBA品牌框叠到内容图上；可选按slots填字与分隔符。"""
    with Image.open(args.base) as base_src, Image.open(args.frame) as frame_src:
        base = ImageOps.exif_transpose(base_src).convert('RGBA')
        frame = ImageOps.exif_transpose(frame_src).convert('RGBA')
        if frame.size != base.size:
            frame = frame.resize(base.size, Image.Resampling.LANCZOS)
        canvas = base.copy()
        canvas.alpha_composite(frame)
        texts = {}
        if args.texts:
            texts = json.loads(Path(args.texts).read_text(encoding='utf-8'))
            if not isinstance(texts, dict):
                raise ValueError('texts 须为 JSON 对象：槽位id → 字符串')
        separators_drawn = 0
        if args.slots:
            slots_doc = json.loads(Path(args.slots).read_text(encoding='utf-8'))
            canvas_size = tuple(slots_doc.get('canvas') or base.size)
            if tuple(canvas_size) != base.size:
                raise ValueError(
                    f'内容图尺寸{base.size}与slots.canvas{canvas_size}不一致，先统一再合成')
            # 先叠框再填字，避免不透明底栏盖住文字
            draw = ImageDraw.Draw(canvas)
            slots_by_id = {}
            for slot in slots_doc.get('slots') or []:
                sid = slot.get('id')
                box = slot.get('box')
                if not sid or not box or len(box) != 4:
                    raise ValueError('每个slot须有id与box[左,上,右,下]')
                slots_by_id[sid] = slot
                text = texts.get(sid, '')
                if not text:
                    continue
                left, top, right, bottom = box
                max_chars = int(slot.get('max_chars') or 40)
                text = text.strip()
                if len(text) > max_chars:
                    text = text[:max_chars]
                height = max(12, bottom - top)
                font, _font_size, _want_bold = _slot_font(slot, height)
                align = slot.get('align') or 'center'
                cx = (left + right) / 2
                cy = (top + bottom) / 2
                anchor = {'left': 'lm', 'right': 'rm', 'center': 'mm'}.get(align, 'mm')
                x = {'left': left, 'right': right, 'center': cx}.get(align, cx)
                # 框上卖点禁止描边；字重只靠粗体字体（如苹方 Semibold）
                draw.text((x, cy), text, fill=slot.get('color') or '#FFFFFF',
                          font=font, anchor=anchor)
            for sep in slots_doc.get('separators') or []:
                x, y, font_size, weight = _separator_points(sep, slots_by_id)
                font, _want_bold = _cjk_font(font_size, weight=weight)
                draw.text((x, y), sep.get('char') or '|',
                          fill=sep.get('color') or '#FFFFFF',
                          font=font, anchor='mm')
                separators_drawn += 1
        save_image(canvas, args.output)
        report({
            'base': args.base, 'frame': args.frame, 'output': args.output,
            'size': list(canvas.size),
            'slots_filled': sorted(k for k, v in texts.items() if v) if texts else [],
            'separators_drawn': separators_drawn,
            'note': '仅叠框、填槽与可选分隔，不修改产品像素内容。'
        })


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(args):
    """输出文件 SHA-256，供模板壳/示意复用比对。"""
    path = Path(args.input)
    if not path.is_file():
        raise ValueError(f'不是文件: {path}')
    report({'file': str(path.resolve()), 'sha256': file_sha256(path),
            'bytes': path.stat().st_size})


def validate_slots(args):
    """结构校验 slots.json；可选对照壳图尺寸。不判断卖点文案对错。"""
    doc = json.loads(Path(args.slots).read_text(encoding='utf-8'))
    issues = []
    canvas = doc.get('canvas')
    if not (isinstance(canvas, list) and len(canvas) == 2
            and all(isinstance(x, int) and x > 0 for x in canvas)):
        issues.append('canvas 须为 [宽, 高] 正整数')
        canvas = [0, 0]
    cw, ch = canvas[0], canvas[1]
    slots = doc.get('slots')
    if not isinstance(slots, list) or not slots:
        issues.append('slots 须为非空数组')
        slots = []
    seen = set()
    for i, slot in enumerate(slots):
        sid = slot.get('id')
        box = slot.get('box')
        max_chars = slot.get('max_chars')
        if not sid or not isinstance(sid, str):
            issues.append(f'slots[{i}] 缺 id')
        elif sid in seen:
            issues.append(f'重复 id: {sid}')
        else:
            seen.add(sid)
        if not (isinstance(box, list) and len(box) == 4
                and all(isinstance(x, int) for x in box)):
            issues.append(f'slots[{i}] box 须为 [左,上,右,下] 整数')
        else:
            left, top, right, bottom = box
            if not (0 <= left < right <= cw and 0 <= top < bottom <= ch):
                issues.append(f'slots[{i}] box 超出 canvas 或不合法: {box}')
        if not (isinstance(max_chars, int) and max_chars > 0):
            issues.append(f'slots[{i}] max_chars 须为正整数')
        font_size = slot.get('font_size')
        if font_size is not None and not (isinstance(font_size, int) and font_size > 0):
            issues.append(f'slots[{i}] font_size 须为正整数')
        font_scale = slot.get('font_scale')
        if font_scale is not None and not (
                isinstance(font_scale, (int, float)) and 0 < float(font_scale) <= 1.5):
            issues.append(f'slots[{i}] font_scale 须为 (0, 1.5] 数值')
        weight = slot.get('font_weight')
        if weight is not None and not isinstance(weight, str):
            issues.append(f'slots[{i}] font_weight 须为字符串')
        if font_size is None and font_scale is None:
            issues.append(
                f'slots[{i}] 须写 font_size 或 font_scale（对照示意，禁止依赖过小默认）')
    for i, sep in enumerate(doc.get('separators') or []):
        if not isinstance(sep, dict):
            issues.append(f'separators[{i}] 须为对象')
            continue
        if 'x' in sep and 'y' in sep:
            if not all(isinstance(sep.get(k), (int, float)) for k in ('x', 'y')):
                issues.append(f'separators[{i}] x,y 须为数值')
        else:
            pair = sep.get('between')
            if not (isinstance(pair, list) and len(pair) == 2
                    and all(isinstance(x, str) for x in pair)):
                issues.append(f'separators[{i}] 须有 x,y 或 between:[id1,id2]')
            elif seen and any(x not in seen for x in pair):
                issues.append(f'separators[{i}] between 引用未知槽 id')
    shell_info = None
    if args.shell:
        shell = Path(args.shell)
        if not shell.is_file():
            issues.append(f'壳文件不存在: {shell}')
        else:
            with Image.open(shell) as im:
                size = list(ImageOps.exif_transpose(im).size)
            shell_info = {'path': str(shell.resolve()), 'size': size,
                          'sha256': file_sha256(shell)}
            if cw and ch and size != [cw, ch]:
                issues.append(f'壳尺寸 {size} 与 slots.canvas {[cw, ch]} 不一致')
    ok = not issues
    report({
        'ok': ok, 'slots_file': args.slots, 'slot_count': len(slots),
        'canvas': canvas, 'shell': shell_info, 'issues': issues,
        'note': '仅结构校验；满长看图自检仍须人工完成。'
    })
    if not ok:
        raise ValueError('validate-slots 未通过: ' + '; '.join(issues))


def preview(args):
    files = getattr(args, 'files', None)
    if files is None:
        files = inputs(args.input)
    if not files:
        raise ValueError('No images: refusing to create an empty preview.')
    output = Path(args.output).resolve()
    if any(p.resolve() == output for p in files):
        raise ValueError('Preview output must be outside the input image set.')
    tiles = []
    background = getattr(args, 'background', 'white')
    for path in files:
        with Image.open(path) as src:
            im = ImageOps.exif_transpose(src).convert('RGBA')
            if args.kind == 'detail':
                im = im.resize((args.width, max(1, round(im.height * args.width / im.width))), Image.Resampling.LANCZOS)
                tile = Image.new('RGB', im.size, background)
                tile.paste(im, mask=im.getchannel('A'))
            else:
                im.thumbnail((args.width, args.width), Image.Resampling.LANCZOS)
                tile = Image.new('RGB', (args.width, args.width), background)
                tile.paste(im, ((args.width-im.width)//2, (args.width-im.height)//2), im)
            tiles.append(tile)
    if args.kind == 'detail':
        canvas = Image.new('RGB', (args.width, sum(t.height for t in tiles)), background)
        y = 0
        for tile in tiles:
            canvas.paste(tile, (0, y)); y += tile.height
    else:
        columns = min(args.columns, len(tiles))
        canvas = Image.new('RGB', (args.width*columns, args.width*math.ceil(len(tiles)/columns)), background)
        for i, tile in enumerate(tiles):
            canvas.paste(tile, ((i % columns)*args.width, (i // columns)*args.width))
    save_image(canvas, args.output)
    report({'preview': args.output, 'files_in_order': [p.name for p in files], 'size': canvas.size})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('inspect'); check.add_argument('input'); check.add_argument('--report')
    exp = sub.add_parser('export'); exp.add_argument('input'); exp.add_argument('output')
    exp.add_argument('--width', type=int, required=True); exp.add_argument('--square', action='store_true')
    pre = sub.add_parser('preview'); pre.add_argument('kind', choices=['main', 'detail'])
    pre.add_argument('input'); pre.add_argument('output'); pre.add_argument('--width', type=int, default=400)
    pre.add_argument('--columns', type=int, default=3)
    count = sub.add_parser('count'); count.add_argument('references'); count.add_argument('delivered')
    count.add_argument('--report')
    frame = sub.add_parser('composite-frame')
    frame.add_argument('base'); frame.add_argument('frame'); frame.add_argument('output')
    frame.add_argument('--slots', help='可选slots.json路径')
    frame.add_argument('--texts', help='可选槽位文案JSON：id→字符串')
    fp = sub.add_parser('fingerprint'); fp.add_argument('input')
    vs = sub.add_parser('validate-slots'); vs.add_argument('slots')
    vs.add_argument('--shell', help='可选壳PNG，核对尺寸并输出指纹')
    args = parser.parse_args()
    if getattr(args, 'width', 1) < 1 or getattr(args, 'columns', 1) < 1:
        raise ValueError('Width and columns must be positive.')
    if args.command == 'inspect':
        report([inspect(p) for p in inputs(args.input)], args.report)
    elif args.command == 'export':
        export(args)
    elif args.command == 'preview':
        preview(args)
    elif args.command == 'composite-frame':
        composite_frame(args)
    elif args.command == 'fingerprint':
        fingerprint(args)
    elif args.command == 'validate-slots':
        validate_slots(args)
    else:
        # Names are the reference IDs; do not renumber to conceal missing items.
        refs = inputs(args.references); delivered = inputs(args.delivered)
        r = {p.stem for p in refs}; d = {p.stem for p in delivered}
        report({'reference_files': len(refs), 'delivered_files': len(delivered),
                'missing_ids': sorted(r-d), 'unexpected_ids': sorted(d-r),
                'duplicate_reference_ids': len(refs) != len(r),
                'duplicate_delivered_ids': len(delivered) != len(d)}, args.report)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
