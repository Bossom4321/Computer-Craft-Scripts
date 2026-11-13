#!/usr/bin/env python3
"""
image_to_16bit_txt_pair.py

Optimized version of the original script:
- Precomputes palette Labs and averaged-pair Labs
- Caches rgb->Lab conversions for source pixels
- Iterates pixels via getdata() for C-level speed
- Localizes hot functions/vars in loops
- Preserves original behavior and CLI flags (--nearest, --visual)
"""
import os
import sys
import traceback
from math import pow
from time import time
from PIL import Image

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

PALETTE_ITEMS = list(PALETTE.items())  # list of (key, (r,g,b))

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
                h = int(round(img_h * scale/1.4))
                if h <= 0:
                    h = 1
                return w, h
            if h_str and not w_str:
                h = int(h_str)
                if h <= 0:
                    print("Height must be a positive integer.")
                    continue
                scale = h / img_h
                w = int(round(img_w * scale*1.4))
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

# Color conversion utilities: sRGB -> linear -> XYZ -> Lab
def srgb_comp_to_linear(v):
    v = v / 255.0
    if v <= 0.04045:
        return v / 12.92
    return pow((v + 0.055) / 1.055, 2.4)

def rgb_to_linear(rgb):
    return (srgb_comp_to_linear(rgb[0]),
            srgb_comp_to_linear(rgb[1]),
            srgb_comp_to_linear(rgb[2]))

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

def lab_distance_sq(a, b):
    return (a[0] - b[0])**2 + (a[1] - b[1])**2 + (a[2] - b[2])**2

# Precompute Lab for palette single colors
PALETTE_LAB = [(k, rgb_to_lab(v)) for k, v in PALETTE_ITEMS]

# coverage fractions: foreground covers ~33% of the pixel
FG_COVERAGE = 0.33
BG_COVERAGE = 1.0 - FG_COVERAGE

# Precompute averaged-pair Lab for all ordered pairs (bg, fg) using weighted mix
PAIR_LABS = []
for bg_k, bg_col in PALETTE_ITEMS:
    for fg_k, fg_col in PALETTE_ITEMS:
        mix_rgb = (
            int(round(bg_col[0] * BG_COVERAGE + fg_col[0] * FG_COVERAGE)),
            int(round(bg_col[1] * BG_COVERAGE + fg_col[1] * FG_COVERAGE)),
            int(round(bg_col[2] * BG_COVERAGE + fg_col[2] * FG_COVERAGE)),
        )
        mix_lab = rgb_to_lab(mix_rgb)
        PAIR_LABS.append((bg_k, fg_k, mix_lab))



# Simple cache for rgb->lab conversions to avoid recomputing in tight loops
_rgb_lab_cache = {}

def rgb_to_lab_cached(rgb):
    key = (rgb[0], rgb[1], rgb[2])
    lab = _rgb_lab_cache.get(key)
    if lab is None:
        lab = rgb_to_lab(key)
        _rgb_lab_cache[key] = lab
    return lab

def normalize_key_char(k):
    if isinstance(k, int):
        if 0 <= k <= 9:
            return str(k)
        return format(k, 'x')
    return str(k).lower()

def best_bg_fg_pair_improved_fast(rgb):
    """
    Faster version using precomputed single-color and pair labs and a small cache.
    """
    src_lab = rgb_to_lab_cached(rgb)

    # first: best single-color (bg==fg)
    best_dist = None
    best_pair = None
    for k, lab in PALETTE_LAB:
        d = (src_lab[0]-lab[0])**2 + (src_lab[1]-lab[1])**2 + (src_lab[2]-lab[2])**2
        if best_dist is None or d < best_dist:
            best_dist = d
            best_pair = (k, k)

    # then: check averaged pairs using precomputed labs
    for bg_k, fg_k, mix_lab in PAIR_LABS:
        d = (src_lab[0]-mix_lab[0])**2 + (src_lab[1]-mix_lab[1])**2 + (src_lab[2]-mix_lab[2])**2
        if d < best_dist:
            best_dist = d
            best_pair = (bg_k, fg_k)

    return best_pair

def make_mapped_visual(resized, mapping_func, out_path='mapped_visual.png'):
    w, h = resized.size
    out = Image.new('RGB', (w, h))
    pixels = list(resized.getdata())
    idx = 0
    for y in range(h):
        for x in range(w):
            rgb = pixels[idx]
            idx += 1
            bgk, fgk = mapping_func(rgb)
            bgc = PALETTE[bgk]
            fgc = PALETTE[fgk]
            mix = ( int(round(bgc[0] * BG_COVERAGE + fgc[0] * FG_COVERAGE)), int(round(bgc[1] * BG_COVERAGE + fgc[1] * FG_COVERAGE)), int(round(bgc[2] * BG_COVERAGE + fgc[2] * FG_COVERAGE)), )
            out.putpixel((x, y), mix)
    out.save(out_path)
    print(f"Wrote {out_path}")

def parse_args():
    # Very small arg parsing: --nearest and --visual allowed
    args = {'nearest': False, 'visual': False}
    for a in sys.argv[1:]:
        if a.lower() == '--nearest':
            args['nearest'] = True
        if a.lower() == '--visual':
            args['visual'] = True
    return args

def log_progress(processed, total, start_time):
    pct = (processed / total) * 100.0 if total else 100.0
    elapsed = time() - start_time
    per_pixel = elapsed / processed if processed else 0.0
    remaining = (total - processed) * per_pixel if processed else 0.0
    sys.stdout.write(f"\rProcessed {processed}/{total} pixels ({pct:5.1f}%) Elapsed {elapsed:5.1f}s ETA {remaining:5.1f}s")
    sys.stdout.flush()

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
        print(f"Mapping {total_pixels} pixels ({w} x {h})...")
        start_time = time()

        # Use fast mapping function and iterate pixels via getdata()
        pixels = list(resized.getdata())
        processed = 0
        out_lines = []
        update_every_rows = max(1, h // 40)  # ~40 updates across the image

        normalize = normalize_key_char
        map_func = best_bg_fg_pair_improved_fast

        idx = 0
        for y in range(h):
            row_parts = []
            row_end = idx + w
            # tight inner loop uses localized names for speed
            while idx < row_end:
                rgb = pixels[idx]
                bgk, fgk = map_func(rgb)
                row_parts.append(normalize(bgk))
                row_parts.append(normalize(fgk))
                
                idx += 1
                processed += 1
            out_lines.append(''.join(row_parts))
            if (y % update_every_rows) == 0 or y == h - 1:
                log_progress(processed, total_pixels, start_time)

        # final newline after progress line
        sys.stdout.write("\n")

        base, _ = os.path.splitext(image_name)
        output_filename = f"{base}.nfp"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out_lines))

        elapsed_total = time() - start_time
        print(f"Wrote: {output_filename} ({w} x {h}) — two characters per pixel (bg then fg)")
        print(f"Completed {total_pixels} pixels in {elapsed_total:5.1f}s ({total_pixels/elapsed_total if elapsed_total>0 else 0:.1f} px/s)")

        if args['visual']:
            make_mapped_visual(resized, map_func)

    except Exception:
        print("Unexpected error:")
        traceback.print_exc()
    finally:
        input("Press Enter to exit...")

if __name__ == '__main__':
    main()
