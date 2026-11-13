#!/usr/bin/env python3
"""
image_to_16bit_txt_pair.py (modified with 3 blend modes, optimized)

Adds run-length compression on each output line:
- Runs longer than 2 of the same character are encoded as: ccxN
  where cc are the first two characters and N = run_length - 2
- Compression is only used if it shortens the output.
- A dash '-' is inserted after a compressed token when the next character
  is alphanumeric to avoid ambiguity during decompression.

Now supports 3 blend ratios:
! = fg 33%,  bg 66%
@ = fg 50%,  bg 50%
# = fg 18.5%, bg 81.5%

Each pixel outputs: [symbol][bg][fg]
Example: !2f@3f@43#34

Optimizations:
- Cache Lab for RGB values
- Prefer pure palette colors when close enough
- Cache best (symbol, bg, fg) for repeated RGBs (no-dither / visual)
"""

import os
import sys
import traceback
from math import pow, sqrt, cos, sin, exp, pi, atan2
from time import time
from PIL import Image, ImageFilter
from numba import njit

# 16-color palette mapping: key -> (R, G, B)
PALETTE = {
    0:    (240, 240, 240),
    1:    (242, 178, 51),
    2:    (229, 127, 216),
    3:    (153, 178, 242),
    4:    (222, 222, 108),
    5:    (127, 204, 25),
    6:    (242, 178, 204),
    7:    (76, 76, 76),
    8:    (153, 153, 153),
    9:    (76, 153, 178),
    "a": (178, 102, 229),
    "b": (51, 102, 204),
    "c": (127, 102, 76),
    "d": (87, 166, 78),
    "e": (204, 76, 76),
    "f": (17, 17, 17),
}

# If a pure palette color is within this ΔE, prefer it over blends
BASE_PRIORITY_THRESHOLD = 8.0

PALETTE_ITEMS = list(PALETTE.items())  # list of (key, (r,g,b))

# aspect ratio correction for character cells (width:height)
ASPECT_RATIO = 1.4  # can be tuned to your glyph's real aspect

# Three blend modes: symbol -> (fg_coverage, bg_coverage)
BLENDS = {
    "!": (0.33, 0.67),
    "@": (0.50, 0.50),
    "#": (0.185, 0.815),
}


def ensure_script_cwd():
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
    os.chdir(script_dir)


def find_png_files():
    return [f for f in os.listdir('.') if f.lower().endswith('.png')]


def choose_file(png_files):
    if not png_files:
        print("No PNG files found in script directory.")
        return None
    if len(png_files) == 1:
        return png_files[0]
    print("PNG files found:")
    for i, name in enumerate(png_files, 1):
        print(f"  {i}. {name}")
    while True:
        choice = input(f"Choose file number (1-{len(png_files)}) or type filename: ").strip()
        if not choice:
            continue
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(png_files):
                return png_files[idx - 1]
        elif choice in png_files:
            return choice
        else:
            print("Invalid selection, try again.")


def get_dimensions(default_w, default_h, img_w, img_h):
    while True:
        w_str = input(f"Enter new width [{default_w}] (leave blank to auto-scale from height): ").strip()
        h_str = input(f"Enter new height [{default_h}] (leave blank to auto-scale from width): ").strip()
        try:
            if not w_str and not h_str:
                return int(default_w), int(default_h)
            if w_str and not h_str:
                w = int(w_str)
                if w <= 0:
                    print("Width must be a positive integer.")
                    continue
                scale = w / img_w
                h = int(round(img_h * scale / ASPECT_RATIO))
                if h <= 0:
                    h = 1
                return w, h
            if h_str and not w_str:
                h = int(h_str)
                if h <= 0:
                    print("Height must be a positive integer.")
                    continue
                scale = h / img_h
                w = int(round(img_w * scale * ASPECT_RATIO))
                if w <= 0:
                    w = 1
                return w, h
            w = int(w_str) if w_str else int(default_w)
            h = int(h_str) if h_str else int(default_h)
            if w <= 0 or h <= 0:
                print("Width and height must be positive integers.")
                continue
            return w, h
        except ValueError:
            print("Invalid integer. Try again.")


# Color conversion utilities: sRGB <-> linear -> XYZ -> Lab

def srgb_comp_to_linear(v):
    v = v / 255.0
    if v <= 0.04045:
        return v / 12.92
    return pow((v + 0.055) / 1.055, 2.4)


def linear_to_srgb_comp(v):
    if v <= 0.0031308:
        v = 12.92 * v
    else:
        v = 1.055 * pow(v, 1.0 / 2.4) - 0.055
    return max(0, min(255, int(round(v * 255.0))))


def rgb_to_linear(rgb):
    return (srgb_comp_to_linear(rgb[0]),
            srgb_comp_to_linear(rgb[1]),
            srgb_comp_to_linear(rgb[2]))


def linear_to_rgb(lr, lg, lb):
    return (linear_to_srgb_comp(lr),
            linear_to_srgb_comp(lg),
            linear_to_srgb_comp(lb))


def linear_to_xyz(lr, lg, lb):
    # sRGB D65
    x = lr * 0.4124564 + lg * 0.3575761 + lb * 0.1804375
    y = lr * 0.2126729 + lg * 0.7151522 + lb * 0.0721750
    z = lr * 0.0193339 + lg * 0.1191920 + lb * 0.9503041
    return (x, y, z)


def f_xyz(t):
    if t > 0.008856:
        return pow(t, 1.0 / 3.0)
    return 7.787 * t + 16.0 / 116.0


def xyz_to_lab(x, y, z):
    # reference white D65
    xr, yr, zr = x / 0.95047, y / 1.00000, z / 1.08883
    fx, fy, fz = f_xyz(xr), f_xyz(yr), f_xyz(zr)
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return (L, a, b)


def rgb_to_lab(rgb):
    lr, lg, lb = rgb_to_linear(rgb)
    x, y, z = linear_to_xyz(lr, lg, lb)
    return xyz_to_lab(x, y, z)


# ΔE2000 implementation

@njit(fastmath=True)
def delta_e_2000(lab1, lab2):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    # Step 1: Chroma
    C1 = sqrt(a1*a1 + b1*b1)
    C2 = sqrt(a2*a2 + b2*b2)
    avg_C = (C1 + C2) * 0.5

    # Step 2: Compensation factor G
    avg_C7 = avg_C**7
    G = 0.5 * (1.0 - sqrt(avg_C7 / (avg_C7 + 25.0**7)))

    # Adjusted a*
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2

    # Adjusted chroma
    C1p = sqrt(a1p*a1p + b1*b1)
    C2p = sqrt(a2p*a2p + b2*b2)

    # Step 3: Hue angles
    h1p = atan2(b1, a1p)
    if h1p < 0.0:
        h1p += 2.0 * pi

    h2p = atan2(b2, a2p)
    if h2p < 0.0:
        h2p += 2.0 * pi

    # Step 4: ΔL', ΔC'
    dLp = L2 - L1
    dCp = C2p - C1p

    # Step 5: Δh'
    if C1p * C2p == 0.0:
        dhp = 0.0
    else:
        dh = h2p - h1p
        if dh > pi:
            dh -= 2.0 * pi
        elif dh < -pi:
            dh += 2.0 * pi
        dhp = 2.0 * sqrt(C1p * C2p) * sin(dh * 0.5)

    # Step 6: Averages
    avg_Lp = 0.5 * (L1 + L2)
    avg_Cp = 0.5 * (C1p + C2p)

    # Average hue
    if C1p * C2p == 0.0:
        avg_hp = h1p + h2p
    else:
        dh = abs(h1p - h2p)
        if dh > pi:
            if (h1p + h2p) < 2.0 * pi:
                avg_hp = (h1p + h2p + 2.0 * pi) * 0.5
            else:
                avg_hp = (h1p + h2p - 2.0 * pi) * 0.5
        else:
            avg_hp = 0.5 * (h1p + h2p)

    # Convert avg hue to degrees for the T term
    avg_hp_deg = avg_hp * 180.0 / pi

    # Step 7: T factor
    T = (
        1.0
        - 0.17 * cos((avg_hp_deg - 30.0) * pi/180.0)
        + 0.24 * cos((2.0 * avg_hp_deg) * pi/180.0)
        + 0.32 * cos((3.0 * avg_hp_deg + 6.0) * pi/180.0)
        - 0.20 * cos((4.0 * avg_hp_deg - 63.0) * pi/180.0)
    )

    # Step 8: Rotation term
    d_ro = 30.0 * exp(-(((avg_hp_deg - 275.0) / 25.0)**2))
    Rc = 2.0 * sqrt((avg_Cp**7) / (avg_Cp**7 + 25.0**7))
    Rt = -sin(2.0 * d_ro * pi/180.0) * Rc

    # Step 9: Scaling factors
    Sl = 1.0 + (0.015 * ((avg_Lp - 50.0)**2)) / sqrt(20.0 + (avg_Lp - 50.0)**2)
    Sc = 1.0 + 0.045 * avg_Cp
    Sh = 1.0 + 0.015 * avg_Cp * T

    # Step 10: Final ΔE2000
    dE = sqrt(
        (dLp / Sl)**2 +
        (dCp / Sc)**2 +
        (dhp / Sh)**2 +
        Rt * (dCp / Sc) * (dhp / Sh)
    )

    return dE


# Simple cache for rgb->lab conversions
_rgb_lab_cache = {}

# Cache for best (symbol, bg, fg) per RGB (used where error is not injected)
BEST_TRIPLET_CACHE = {}


def rgb_to_lab_cached(rgb):
    key = (rgb[0], rgb[1], rgb[2])
    lab = _rgb_lab_cache.get(key)
    if lab is None:
        lab = rgb_to_lab(key)
        _rgb_lab_cache[key] = lab
    return lab


# Precompute Lab for palette single colors
PALETTE_LAB = [(k, rgb_to_lab(v)) for k, v in PALETTE_ITEMS]


def build_candidates_for_blend(fg_cov, bg_cov):
    """
    Build candidate list for a given blend ratio.
    Returns list of (bg_k, fg_k, lab).
    """
    candidates = []

    # Base colors (bg == fg): pure palette colors
    for k, rgb in PALETTE_ITEMS:
        lab = rgb_to_lab(rgb)
        candidates.append((k, k, lab))

    # Mixed colors using linear-RGB weighted blending
    for bg_k, bg_col in PALETTE_ITEMS:
        for fg_k, fg_col in PALETTE_ITEMS:
            if bg_k == fg_k:
                continue  # already included as base color
            bg_lr, bg_lg, bg_lb = rgb_to_linear(bg_col)
            fg_lr, fg_lg, fg_lb = rgb_to_linear(fg_col)
            mix_lr = bg_lr * bg_cov + fg_lr * fg_cov
            mix_lg = bg_lg * bg_cov + fg_lg * fg_cov
            mix_lb = bg_lb * bg_cov + fg_lb * fg_cov
            mix_rgb = linear_to_rgb(mix_lr, mix_lg, mix_lb)
            mix_lab = rgb_to_lab(mix_rgb)
            candidates.append((bg_k, fg_k, mix_lab))

    return candidates


# Build candidate lists for each blend mode
CANDIDATES_BY_MODE = {}
for symbol, (fg_cov, bg_cov) in BLENDS.items():
    CANDIDATES_BY_MODE[symbol] = build_candidates_for_blend(fg_cov, bg_cov)


def normalize_key_char(k):
    if isinstance(k, int):
        if 0 <= k <= 9:
            return str(k)
        return format(k, 'x')
    return str(k).lower()


def find_best_triplet_for_lab_with_lab(src_lab):
    """
    Prefer pure palette colors (bg == fg) if they are close enough.
    Otherwise, fall back to full blend search across all modes.
    """

    # Step 1: Try pure palette colors first
    best_base_dist = None
    best_base_k = None
    best_base_lab = None

    for k, pal_lab in PALETTE_LAB:
        d = delta_e_2000(src_lab, pal_lab)
        if best_base_dist is None or d < best_base_dist:
            best_base_dist = d
            best_base_k = k
            best_base_lab = pal_lab

    # If the best pure palette color is close enough, use it
    if best_base_dist is not None and best_base_dist <= BASE_PRIORITY_THRESHOLD:
        return "!", best_base_k, best_base_k, best_base_lab

    # Step 2: Fall back to full blend search
    best_dist = None
    best_symbol = None
    best_bg = None
    best_fg = None
    best_lab = None

    for symbol, cand_list in CANDIDATES_BY_MODE.items():
        for bg_k, fg_k, cand_lab in cand_list:
            d = delta_e_2000(src_lab, cand_lab)
            if best_dist is None or d < best_dist:
                best_dist = d
                best_symbol = symbol
                best_bg = bg_k
                best_fg = fg_k
                best_lab = cand_lab

    return best_symbol, best_bg, best_fg, best_lab


def find_best_triplet_for_lab(src_lab):
    symbol, bg_k, fg_k, _ = find_best_triplet_for_lab_with_lab(src_lab)
    return symbol, bg_k, fg_k


def find_best_triplet_for_rgb(rgb):
    """
    Best mapping for a given RGB, with caching to avoid recomputing
    for repeated colors (no dithering / visual).
    """
    key = (rgb[0], rgb[1], rgb[2])
    cached = BEST_TRIPLET_CACHE.get(key)
    if cached is not None:
        return cached

    src_lab = rgb_to_lab_cached(rgb)
    symbol, bg_k, fg_k = find_best_triplet_for_lab(src_lab)
    BEST_TRIPLET_CACHE[key] = (symbol, bg_k, fg_k)
    return symbol, bg_k, fg_k


def make_mapped_visual(resized, mapping_func, out_path='mapped_visual.png'):
    """
    Visual preview using whatever blend mode the mapper chose per pixel.
    """
    w, h = resized.size
    out = Image.new('RGB', (w, h))
    pixels = list(resized.getdata())
    idx = 0
    for y in range(h):
        for x in range(w):
            rgb = pixels[idx]
            idx += 1
            symbol, bgk, fgk = mapping_func(rgb)
            bgc = PALETTE[bgk]
            fgc = PALETTE[fgk]
            fg_cov, bg_cov = BLENDS[symbol]
            bg_lr, bg_lg, bg_lb = rgb_to_linear(bgc)
            fg_lr, fg_lg, fg_lb = rgb_to_linear(fgc)
            mix_lr = bg_lr * bg_cov + fg_lr * fg_cov
            mix_lg = bg_lg * bg_cov + fg_lg * fg_cov
            mix_lb = bg_lb * bg_cov + fg_lb * fg_cov
            mix_rgb = linear_to_rgb(mix_lr, mix_lg, mix_lb)
            out.putpixel((x, y), mix_rgb)
    out.save(out_path)
    print(f"Wrote {out_path}")


def parse_args():
    # Args: --nearest, --visual, --dither [none|bayer|floyd]
    args = {'nearest': False, 'visual': False, 'dither': 'bayer'}
    a_iter = iter(sys.argv[1:])
    for a in a_iter:
        al = a.lower()
        if al == '--nearest':
            args['nearest'] = True
        elif al == '--visual':
            args['visual'] = True
        elif al == '--dither':
            try:
                mode = next(a_iter).lower()
            except StopIteration:
                mode = 'bayer'
            if mode in ('none', 'bayer', 'floyd'):
                args['dither'] = mode
            else:
                print(f"Unknown dither mode '{mode}', using 'bayer'.")
                args['dither'] = 'bayer'
    return args


def log_progress(processed, total, start_time):
    pct = (processed / total) * 100.0 if total else 100.0
    elapsed = time() - start_time
    per_pixel = elapsed / processed if processed else 0.0
    remaining = (total - processed) * per_pixel if processed else 0.0
    sys.stdout.write(f"\rProcessed {processed}/{total} pixels ({pct:5.1f}%) Elapsed {elapsed:5.1f}s ETA {remaining:5.1f}s")
    sys.stdout.flush()


# Dithering utilities

BAYER_4x4 = [
    [0,  8,  2, 10],
    [12, 4, 14,  6],
    [3, 11,  1,  9],
    [15, 7, 13,  5],
]
BAYER_SCALE = 1.0  # how strong the dither affects L*


def apply_bayer_offset(lab, x, y):
    L, a, b = lab
    t = BAYER_4x4[y % 4][x % 4] / 15.0  # 0..1
    offset = (t - 0.5) * BAYER_SCALE    # -0.5..+0.5 scaled
    return (L + offset, a, b)


def floyd_steinberg_dither(resized, start_time=None):
    """
    Error diffusion in Lab space, using all three blend modes per pixel.
    Note: cannot cache results here because Lab is modified by error.
    """
    w, h = resized.size
    pixels = list(resized.getdata())
    total_pixels = w * h
    out_triplets = [[('!', 0, 0)] * w for _ in range(h)]

    # error buffer for Lab
    errL = [[0.0] * w for _ in range(h)]
    erra = [[0.0] * w for _ in range(h)]
    errb = [[0.0] * w for _ in range(h)]

    processed = 0

    for y in range(h):
        for x in range(w):
            idx = y * w + x
            rgb = pixels[idx]
            base_lab = rgb_to_lab_cached(rgb)
            L = base_lab[0] + errL[y][x]
            a = base_lab[1] + erra[y][x]
            b = base_lab[2] + errb[y][x]
            cur_lab = (L, a, b)

            symbol, bgk, fgk, cand_lab = find_best_triplet_for_lab_with_lab(cur_lab)
            out_triplets[y][x] = (symbol, bgk, fgk)

            eL = L - cand_lab[0]
            ea = a - cand_lab[1]
            eb = b - cand_lab[2]

            # distribute error
            if x + 1 < w:
                errL[y][x + 1] += eL * 7 / 16.0
                erra[y][x + 1] += ea * 7 / 16.0
                errb[y][x + 1] += eb * 7 / 16.0
            if y + 1 < h:
                if x > 0:
                    errL[y + 1][x - 1] += eL * 3 / 16.0
                    erra[y + 1][x - 1] += ea * 3 / 16.0
                    errb[y + 1][x - 1] += eb * 3 / 16.0
                errL[y + 1][x] += eL * 5 / 16.0
                erra[y + 1][x] += ea * 5 / 16.0
                errb[y + 1][x] += eb * 5 / 16.0
                if x + 1 < w:
                    errL[y + 1][x + 1] += eL * 1 / 16.0
                    erra[y + 1][x + 1] += ea * 1 / 16.0
                    errb[y + 1][x + 1] += eb * 1 / 16.0

            processed += 1
            if start_time and processed % (w * max(1, h // 40)) == 0:
                log_progress(processed, total_pixels, start_time)

    return out_triplets


def bayer_dither(resized, start_time=None):
    w, h = resized.size
    pixels = list(resized.getdata())
    total_pixels = w * h
    out_triplets = [[('!', 0, 0)] * w for _ in range(h)]
    processed = 0

    for y in range(h):
        for x in range(w):
            idx = y * w + x
            rgb = pixels[idx]
            base_lab = rgb_to_lab_cached(rgb)
            d_lab = apply_bayer_offset(base_lab, x, y)
            symbol, bgk, fgk = find_best_triplet_for_lab(d_lab)
            out_triplets[y][x] = (symbol, bgk, fgk)
            processed += 1
        if start_time and (y % max(1, h // 40) == 0 or y == h - 1):
            log_progress(processed, total_pixels, start_time)

    return out_triplets


def no_dither(resized, start_time=None):
    """
    No error diffusion or spatial dither.
    Uses caching of best_triplet_per_rgb for speed.
    """
    w, h = resized.size
    pixels = list(resized.getdata())
    total_pixels = w * h
    out_triplets = [[('!', 0, 0)] * w for _ in range(h)]
    processed = 0

    for y in range(h):
        for x in range(w):
            idx = y * w + x
            rgb = pixels[idx]
            symbol, bgk, fgk = find_best_triplet_for_rgb(rgb)
            out_triplets[y][x] = (symbol, bgk, fgk)
            processed += 1
        if start_time and (y % max(1, h // 40) == 0 or y == h - 1):
            log_progress(processed, total_pixels, start_time)

    return out_triplets


# -------------------------
# Compression helper
# -------------------------
def _is_alnum(ch):
    # treat hex digits and letters as alphanumeric for separator decision
    return ch.isalnum()


def compress_line(line: str) -> str:
    """
    Two-stage compression:
    1. Compress runs of identical single characters -> ccxN-
    2. Compress runs of identical 2-character pairs -> PAIRPAIRxN+
    """

    if not line:
        return line

    # -----------------------------
    # Stage 1: single-character RLE
    # -----------------------------
    out1 = []
    i = 0
    n = len(line)

    while i < n:
        ch = line[i]
        j = i + 1
        while j < n and line[j] == ch:
            j += 1
        run_len = j - i

        if run_len > 2:
            token = f"{ch}{ch}x{run_len - 2}"
            if len(token) < run_len:
                out1.append(token)
                if j < n and line[j].isalnum():
                    out1.append('-')
                i = j
                continue

        out1.append(line[i:j])
        i = j

    stage1 = ''.join(out1)

    # -----------------------------
    # Stage 2: pair compression
    # -----------------------------
    out2 = []
    i = 0
    n = len(stage1)

    while i < n:
        # If not enough chars left for a pair, just append
        if i + 1 >= n:
            out2.append(stage1[i])
            break

        pair = stage1[i:i+2]

        # If the next token starts with x or - or +, it's not a raw pair
        if pair[0] in "x-+" or pair[1] in "x-+":
            out2.append(pair[0])
            i += 1
            continue

        # Count repeated pairs
        j = i + 2
        while j + 1 < n and stage1[j:j+2] == pair:
            j += 2

        run_len = (j - i) // 2

        if run_len > 2:
            token = f"{pair}{pair}x{run_len - 2}"
            # Only compress if shorter
            if len(token) < run_len * 2:
                out2.append(token)
                # Add '+' if next char is alphanumeric
                if j < n and stage1[j].isalnum():
                    out2.append('+')
                i = j
                continue

        # Otherwise output raw
        out2.append(stage1[i:j])
        i = j

    return ''.join(out2)


# -------------------------
# Main
# -------------------------
def main():
    try:
        ensure_script_cwd()
        args = parse_args()

        png_files = find_png_files()
        image_name = choose_file(png_files)
        if not image_name:
            input("Press Enter to exit...")
            return

        try:
            img = Image.open(image_name).convert('RGB')
        except Exception as e:
            print(f"Failed to open '{image_name}': {e}")
            input("Press Enter to exit...")
            return

        # Pre-sharpen before resizing
        img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=150, threshold=3))

        default_w, default_h = img.size
        print(f"Original image size: {default_w} x {default_h}")

        new_w, new_h = get_dimensions(default_w, default_h, default_w, default_h)

        if args['nearest']:
            resample = Image.NEAREST
        else:
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = getattr(Image, 'LANCZOS', Image.BICUBIC)

        resized = img.resize((new_w, new_h), resample)

        w, h = resized.size
        total_pixels = w * h
        print(f"Mapping {total_pixels} pixels ({w} x {h}) with dither='{args['dither']}'...")
        start_time = time()

        # Choose dithering mode
        if args['dither'] == 'floyd':
            triplet_grid = floyd_steinberg_dither(resized, start_time=start_time)
        elif args['dither'] == 'bayer':
            triplet_grid = bayer_dither(resized, start_time=start_time)
        else:
            triplet_grid = no_dither(resized, start_time=start_time)

        # Generate output text lines
        out_lines = []
        normalize = normalize_key_char
        processed = 0

        for y in range(h):
            row_parts = []
            for x in range(w):
                symbol, bgk, fgk = triplet_grid[y][x]
                # file format: symbol, then bg, then fg
                row_parts.append(symbol)
                row_parts.append(normalize(bgk))
                row_parts.append(normalize(fgk))
                processed += 1
            raw_line = ''.join(row_parts)
            # compress the line before writing
            compressed = compress_line(raw_line)
            out_lines.append(compressed)
            if (y % max(1, h // 40) == 0 or y == h - 1):
                log_progress(processed, total_pixels, start_time)

        sys.stdout.write("\n")

        base, _ = os.path.splitext(image_name)
        output_filename = f"{base}.nfp"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out_lines))

        elapsed_total = time() - start_time
        print(f"Wrote: {output_filename} ({w} x {h}) — three characters per pixel (mode, bg, fg) with line compression")
        print(f"Completed {total_pixels} pixels in {elapsed_total:5.1f}s ({total_pixels/elapsed_total if elapsed_total>0 else 0:.1f} px/s)")

        if args['visual']:
            # visual uses no-dither mapping for a clean palette/coverage preview
            make_mapped_visual(resized, find_best_triplet_for_rgb)

    except Exception:
        print("Unexpected error:")
        traceback.print_exc()
    finally:
        input("Press Enter to exit...")


if __name__ == '__main__':
    main()
