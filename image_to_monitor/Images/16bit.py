#!/usr/bin/env python3
"""
image_to_16bit_txt.py

Runs from the script's directory, finds PNG(s) in that directory, resizes to user-specified
dimensions, maps each pixel to the closest color from the 16-color palette, writes a .txt,
and pauses at the end so you can read errors/output.

Behavior change:
- If you leave the width blank and enter a new height, the width is scaled to preserve
  the original aspect ratio.
- If you leave the height blank and enter a new width, the height is scaled to preserve
  the original aspect ratio.
- If you enter both, those exact dimensions are used.
"""

import os
import sys
import traceback
from PIL import Image

# 16-color palette mapping: decimal_value -> (R, G, B)
PALETTE = {
    0:    (240, 240, 240),  # white
    1:    (242, 178, 51),   # orange
    2:    (229, 127, 216),  # magenta
    3:    (153, 178, 242),  # lightBlue
    4:   (222, 222, 108),  # yellow
    5:   (127, 204, 25),   # lime
    6:   (242, 178, 204),  # pink
    7:  (76, 76, 76),     # gray
    8:  (153, 153, 153),  # lightGray
    9:  (76, 153, 178),   # cyan
    "a": (178, 102, 229),  # purple
    "b": (51, 102, 204),   # blue
    "c": (127, 102, 76),   # brown
    "d": (87, 166, 78),    # green
    "e":(204, 76, 76),    # red
    "f":(17, 17, 17),     # black
}

PALETTE_ITEMS = list(PALETTE.items())

def ensure_script_cwd():
    # Determine script directory robustly and chdir into it
    if getattr(sys, 'frozen', False):
        # PyInstaller or similar
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

def fit_size(box_w, box_h, img_w, img_h, round_func=round):
    # compute scale and new dimensions preserving aspect ratio
    s = min(box_w / img_w, box_h / img_h)
    return int(round_func(img_w * s)), int(round_func(img_h * s))

def get_dimensions(default_w, default_h, img_w, img_h):
    """
    Prompt the user for new width and height.
    - If width is blank and height provided: width is scaled to preserve aspect ratio.
    - If height is blank and width provided: height is scaled to preserve aspect ratio.
    - If both provided: use them as-is (must be positive ints).
    - If both blank: use original dimensions.
    """
    while True:
        w_str = input(f"Enter new width [{default_w}] (leave blank to auto-scale from height): ").strip()
        h_str = input(f"Enter new height [{default_h}] (leave blank to auto-scale from width): ").strip()
        try:
            # Both blank -> use defaults
            if not w_str and not h_str:
                return int(default_w), int(default_h)

            # Only width provided -> scale height to preserve aspect ratio
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

            # Only height provided -> scale width to preserve aspect ratio
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

            # Both provided -> use both explicitly
            w = int(w_str) if w_str else int(default_w)
            h = int(h_str) if h_str else int(default_h)
            if w <= 0 or h <= 0:
                print("Width and height must be positive integers.")
                continue
            return w, h
        except ValueError:
            print("Invalid integer. Try again.")

def closest_palette_value(rgb):
    r, g, b = rgb
    best_val = None
    best_dist = None
    for val, (pr, pg, pb) in PALETTE_ITEMS:
        dr = r - pr
        dg = g - pg
        db = b - pb
        dist = dr*dr + dg*dg + db*db
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_val = val
    return best_val

def main():
    try:
        ensure_script_cwd()
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

        # Pass original image size so get_dimensions can scale correctly
        new_w, new_h = get_dimensions(default_w, default_h, default_w, default_h)

        # Resample compatibility fallback
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = getattr(Image, 'LANCZOS', Image.BICUBIC)

        resized = img.resize((new_w, new_h), resample)

        out_lines = []
        for y in range(new_h):
            row = []
            for x in range(new_w):
                rgb = resized.getpixel((x, y))
                val = closest_palette_value(rgb)
                row.append(str(val))
            out_lines.append(''.join(row))

        base, _ = os.path.splitext(image_name)
        output_filename = f"{base}.nfp"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out_lines))

        print(f"Wrote: {output_filename} ({new_w} x {new_h})")
    except Exception:
        print("Unexpected error:")
        traceback.print_exc()
    finally:
        input("Press Enter to exit...")

if __name__ == '__main__':
    main()
