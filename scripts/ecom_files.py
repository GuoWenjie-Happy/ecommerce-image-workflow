"""Reusable file operations only; never generates or retouches product pixels."""
import argparse
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


def _cjk_font(size):
    # ponytail: 常见系统字体探测；找不到则用默认位图字体（中文可能方框）
    candidates = [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simhei.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def composite_frame(args):
    """将RGBA品牌框叠到内容图上；可选按slots.json填入卖点文字。"""
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
        if args.slots:
            slots_doc = json.loads(Path(args.slots).read_text(encoding='utf-8'))
            canvas_size = tuple(slots_doc.get('canvas') or base.size)
            if tuple(canvas_size) != base.size:
                raise ValueError(
                    f'内容图尺寸{base.size}与slots.canvas{canvas_size}不一致，先统一再合成')
            # 先叠框再填字，避免不透明底栏盖住文字
            draw = ImageDraw.Draw(canvas)
            for slot in slots_doc.get('slots') or []:
                sid = slot.get('id')
                box = slot.get('box')
                if not sid or not box or len(box) != 4:
                    raise ValueError('每个slot须有id与box[左,上,右,下]')
                text = texts.get(sid, '')
                if not text:
                    continue
                left, top, right, bottom = box
                max_chars = int(slot.get('max_chars') or 40)
                text = text.strip()
                if len(text) > max_chars:
                    text = text[:max_chars]
                height = max(12, bottom - top)
                font = _cjk_font(max(14, int(height * 0.55)))
                align = slot.get('align') or 'center'
                cx = (left + right) / 2
                cy = (top + bottom) / 2
                anchor = {'left': 'lm', 'right': 'rm', 'center': 'mm'}.get(align, 'mm')
                x = {'left': left, 'right': right, 'center': cx}.get(align, cx)
                draw.text((x, cy), text, fill=slot.get('color') or '#FFFFFF',
                          font=font, anchor=anchor)
        save_image(canvas, args.output)
        report({
            'base': args.base, 'frame': args.frame, 'output': args.output,
            'size': list(canvas.size),
            'slots_filled': sorted(k for k, v in texts.items() if v) if texts else [],
            'note': '仅叠框与可选填槽，不修改产品像素内容。'
        })


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
