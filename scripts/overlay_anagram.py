import re
import sys
from collections import defaultdict
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from svgpathtools import parse_path

SOURCE = "THELMA TERTRAIS"
TARGET = "HAMLET TRAITRES"
FONT_PATH = "assets/Bungee-Regular.ttf"

SNAKE_COLORS = ["#9be9a8", "#40c463", "#30a14e", "#216e39"]
SEGMENT_PX = 5.0


def build_mapping(source, target):
    target_positions = defaultdict(list)
    for i, ch in enumerate(target):
        target_positions[ch].append(i)
    mapping = {}
    used = defaultdict(int)
    for i, ch in enumerate(source):
        idx = target_positions[ch][used[ch]]
        mapping[i] = idx
        used[ch] += 1
    return mapping


def build_overlay(svg_min_x, svg_min_y, svg_w, svg_h):
    font = TTFont(FONT_PATH)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    units_per_em = font["head"].unitsPerEm
    hmtx = font["hmtx"]

    def gname(ch):
        return cmap[ord(ch)]

    def advance(ch):
        return hmtx[gname(ch)][0]

    def path_d(ch):
        pen = SVGPathPen(glyph_set)
        glyph_set[gname(ch)].draw(pen)
        return pen.getCommands()

    gap_units = 0.16 * units_per_em

    def natural_width(word):
        total = 0
        for ch in word:
            total += advance(ch) + gap_units
        return total - gap_units

    def cumulative_positions(word, scale, start_x):
        xs = []
        x = start_x
        for ch in word:
            xs.append(x)
            x += (advance(ch) + gap_units) * scale
        return xs

    mapping = build_mapping(SOURCE, TARGET)

    target_px_width = svg_w * 0.86
    natural = max(natural_width(SOURCE), natural_width(TARGET))
    scale = target_px_width / natural
    font_size_px = scale * units_per_em

    start_x = svg_min_x + (svg_w - natural * scale) / 2
    source_xs = cumulative_positions(SOURCE, scale, start_x)
    target_xs = cumulative_positions(TARGET, scale, start_x)

    baseline_y = svg_min_y + svg_h * 0.52
    arc_height = font_size_px * 0.35
    cap_height_px = font_size_px * 0.72

    target_segment_units = SEGMENT_PX / scale

    def sample_points(ch):
        d = path_d(ch)
        path = parse_path(d)
        total_len = path.length()
        n = max(6, round(total_len / target_segment_units))
        pts = []
        for k in range(n):
            frac = k / n
            pt = path.point(path.ilength(frac * total_len))
            pts.append((pt.real, pt.imag))
        return pts

    unique_letters = sorted(set(SOURCE.replace(" ", "")))
    letter_points = {ch: sample_points(ch) for ch in unique_letters}
    seg_size_units = SEGMENT_PX / scale

    groups = []
    for i, ch in enumerate(SOURCE):
        if ch == " ":
            continue
        j = mapping[i]
        sx, ex = source_xs[i], target_xs[j]
        mx = (sx + ex) / 2
        xv = f"{sx},{baseline_y};{sx},{baseline_y};{mx},{baseline_y-arc_height};{ex},{baseline_y};{ex},{baseline_y};{mx},{baseline_y-arc_height};{sx},{baseline_y}"
        kt = "0;0.14;0.28;0.42;0.64;0.78;1"
        sp = ";".join(["0.42 0 0.58 1"] * 6)

        rects = []
        for k, (px, py) in enumerate(letter_points[ch]):
            color = SNAKE_COLORS[k % len(SNAKE_COLORS)]
            rects.append(
                f'<rect x="{px - seg_size_units/2:.1f}" y="{py - seg_size_units/2:.1f}" '
                f'width="{seg_size_units:.1f}" height="{seg_size_units:.1f}" '
                f'rx="{seg_size_units*0.25:.1f}" fill="{color}"/>'
            )

        groups.append(
            f'<g><animateTransform attributeName="transform" type="translate" '
            f'values="{xv}" keyTimes="{kt}" dur="9s" repeatCount="indefinite" '
            f'calcMode="spline" keySplines="{sp}"/>'
            f'<g transform="scale({scale:.5f},{-scale:.5f})">'
            f'{"".join(rects)}'
            f'</g></g>'
        )

    backing_x = start_x - font_size_px * 0.25
    backing_w = natural * scale + font_size_px * 0.5
    backing_y = baseline_y - cap_height_px - arc_height - font_size_px * 0.15
    backing_h = cap_height_px + arc_height + font_size_px * 0.3

    backing = (
        f'<rect x="{backing_x:.1f}" y="{backing_y:.1f}" width="{backing_w:.1f}" '
        f'height="{backing_h:.1f}" rx="10" fill="#02132b" fill-opacity="0.5"/>'
    )

    overlay = f'{backing}{"".join(groups)}'
    return overlay


def inject(svg_path):
    with open(svg_path, "r") as f:
        content = f.read()

    m = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', content)
    if not m:
        raise RuntimeError("No viewBox found in " + svg_path)
    min_x, min_y, w, h = map(float, m.groups())

    overlay = build_overlay(min_x, min_y, w, h)
    content = content.replace("</svg>", overlay + "</svg>")

    with open(svg_path, "w") as f:
        f.write(content)
    print(f"Injected snake-lettering anagram overlay into {svg_path}")


if __name__ == "__main__":
    for path in sys.argv[1:]:
        inject(path)
