#!/usr/bin/env python3
"""
High-fidelity, optimized image -> 256-combination dither exporter.

Features:
 - Palette order fixed (0..f) and optionally optimized via k-means initialized from base palette.
 - Composite model: composite = bg * 0.66 + fg * 0.33 (weights configurable).
 - Mixing and distance calculations performed in linear RGB and CIE-Lab for perceptual accuracy.
 - Vectorized, block-processed nearest-neighbor search over 256 composites (NumPy).
 - Falls back to exact Python loops if NumPy is not available (slower but identical results).
 - Writes compressed output compatible with the provided Lua readPairsPerLine:
     * Palette line (uncompressed): 0xRRGGBB,0xRRGGBB,...
     * Each row compressed using pair-run tokens and optional single-char tokens.
 - Progress/ETA printed during mapping.
 - Output filename: <input_basename>.wpft
"""

from PIL import Image
import os
import sys
import math
import time
import traceback

# Optional: use numpy for heavy lifting
try:
    import numpy as np
except Exception:
    np = None

# --- Configuration ---
FG_WEIGHT = 0.33
BG_WEIGHT = 1.0 - FG_WEIGHT
KMEANS_SAMPLES = 10000
KMEANS_ITERS = 12
PROGRESS_UPDATE_INTERVAL = 0.5  # seconds
BLOCK_PIXELS = 100_000  # tune for memory/speed (float32: BLOCK_PIXELS x 256 x 3 ~ memory)

# Base palette (hex) in required fixed order (index 0..f)
BASE_PALETTE_HEX = [
    "F0F0F0",  # 0 white
    "F2B233",  # 1 orange
    "E57FD8",  # 2 magenta
    "99B2F2",  # 3 lightblue
    "DEDE6C",  # 4 yellow
    "7FCC19",  # 5 lime
    "F2B2CC",  # 6 pink
    "4C4C4C",  # 7 gray
    "999999",  # 8 lightgray
    "4C99B2",  # 9 cyan
    "B266E5",  # a purple
    "3366CC",  # b blue
    "7F664C",  # c brown
    "57A64E",  # d green
    "CC4C4C",  # e red
    "111111",  # f black
]

HEX_DIGITS = "0123456789abcdef"

# --- Utilities ---
def hex_to_rgb(h):
    h = h.strip()
    if h.startswith("0x") or h.startswith("0X"):
        h = h[2:]
    if len(h) == 3:
        h = ''.join([c*2 for c in h])
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return "{:02X}{:02X}{:02X}".format(*[int(round(max(0, min(255, v)))) for v in rgb])

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
    ASPECT_RATIO = 1.4
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

# --- Color conversions (NumPy vectorized) ---
def srgb_to_linear_np(arr):
    """
    arr: float array in [0,1], shape (...,3)
    returns linear RGB in [0,1]
    """
    a = 0.055
    low_mask = arr <= 0.04045
    out = np.empty_like(arr, dtype=np.float32)
    out[low_mask] = arr[low_mask] / 12.92
    out[~low_mask] = ((arr[~low_mask] + a) / (1 + a)) ** 2.4
    return out

def linear_to_xyz_np(lin):
    """
    lin: linear RGB in [0,1], shape (...,3)
    returns XYZ (D65)
    """
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
    orig_shape = lin.shape
    flat = lin.reshape(-1, 3)
    xyz = flat.dot(M.T)
    return xyz.reshape(orig_shape)

def xyz_to_lab_np(xyz):
    """
    xyz: shape (...,3), using D65 reference white
    returns Lab array same shape
    """
    xr, yr, zr = 0.95047, 1.00000, 1.08883
    x = xyz[..., 0] / xr
    y = xyz[..., 1] / yr
    z = xyz[..., 2] / zr

    eps = 0.008856
    kappa = 903.3

    def f(t):
        mask = t > eps
        out = np.empty_like(t, dtype=np.float32)
        out[mask] = np.cbrt(t[mask])
        out[~mask] = (kappa * t[~mask] + 16.0) / 116.0
        return out

    fx = f(x)
    fy = f(y)
    fz = f(z)

    L = (116.0 * fy) - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    lab = np.stack([L, a, b], axis=-1).astype(np.float32)
    return lab

def rgb8_to_lab_np(rgb8):
    """
    rgb8: uint8 array shape (...,3)
    returns Lab float32 array shape (...,3)
    """
    arr = rgb8.astype(np.float32) / 255.0
    lin = srgb_to_linear_np(arr)
    xyz = linear_to_xyz_np(lin)
    lab = xyz_to_lab_np(xyz)
    return lab

# --- Palette optimization (k-means) ---
def optimize_palette_kmeans(img_rgb_array, base_palette_rgb, k=16, samples=KMEANS_SAMPLES, iters=KMEANS_ITERS):
    """
    Small k-means in RGB space initialized from base palette.
    Returns optimized palette as list of RGB tuples (0..255 ints).
    """
    if np is None:
        return base_palette_rgb
    h, w, _ = img_rgb_array.shape
    total = h * w
    flat = img_rgb_array.reshape(-1, 3).astype(np.float32)
    if total <= samples:
        sample_pixels = flat
    else:
        rng = np.random.default_rng(seed=42)
        idx = rng.choice(total, size=samples, replace=False)
        sample_pixels = flat[idx]

    centroids = np.array(base_palette_rgb, dtype=np.float32)[:k].copy()

    for _ in range(iters):
        dists = np.sum((sample_pixels[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
        labels = np.argmin(dists, axis=1)
        new_centroids = np.zeros_like(centroids)
        for i in range(k):
            mask = labels == i
            if np.any(mask):
                new_centroids[i] = sample_pixels[mask].mean(axis=0)
            else:
                new_centroids[i] = centroids[i] + (np.random.rand(3) - 0.5) * 10.0
        shift = np.linalg.norm(new_centroids - centroids)
        centroids = new_centroids
        if shift < 0.5:
            break
    centroids = np.clip(centroids, 0, 255).astype(int)
    return [tuple(map(int, c)) for c in centroids.tolist()]

# --- Vectorized mapping using Lab distances ---
def convert_image_to_pairs_vectorized(img, palette_rgb, block_pixels=BLOCK_PIXELS):
    """
    Vectorized, perceptual mapping:
      - precompute 256 composites in linear RGB
      - convert composites to Lab
      - convert image pixels to Lab (block processed)
      - compute squared distances and argmin over 256 composites
    Returns list of rows of (bg_idx, fg_idx) tuples.
    """
    w, h = img.size
    arr8 = np.asarray(img.convert("RGB"), dtype=np.uint8)  # (h,w,3)
    flat8 = arr8.reshape(-1, 3)

    pal8 = np.array(palette_rgb, dtype=np.uint8)  # (16,3)
    pal_lin = srgb_to_linear_np(pal8.astype(np.float32) / 255.0)  # (16,3) float32

    comps_lin = np.empty((256, 3), dtype=np.float32)
    idx = 0
    for bi in range(16):
        for fi in range(16):
            comps_lin[idx] = pal_lin[bi] * BG_WEIGHT + pal_lin[fi] * FG_WEIGHT
            idx += 1

    comps_xyz = linear_to_xyz_np(comps_lin)
    comps_lab = xyz_to_lab_np(comps_xyz)  # (256,3)

    total = flat8.shape[0]
    pairs_flat = np.empty((total, 2), dtype=np.uint8)

    start = 0
    last_update = time.time()
    t0 = last_update
    processed = 0
    while start < total:
        end = min(start + block_pixels, total)
        block8 = flat8[start:end].astype(np.float32) / 255.0  # (B,3)
        block_lin = srgb_to_linear_np(block8)
        block_xyz = linear_to_xyz_np(block_lin)
        block_lab = xyz_to_lab_np(block_xyz)  # (B,3)

        diff = block_lab[:, None, :] - comps_lab[None, :, :]
        d2 = np.einsum('ijk,ijk->ij', diff, diff)  # (B,256)
        idxs = np.argmin(d2, axis=1).astype(np.int32)  # (B,)

        pairs_flat[start:end, 0] = (idxs // 16).astype(np.uint8)
        pairs_flat[start:end, 1] = (idxs % 16).astype(np.uint8)

        processed += (end - start)
        now = time.time()
        if now - last_update >= PROGRESS_UPDATE_INTERVAL:
            elapsed = now - t0
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = total - processed
            eta = remaining / rate if rate > 0 else float('inf')
            print_progress(processed, total, eta)
            last_update = now

        start = end

    print_progress(total, total, 0.0)

    pairs_rows = []
    flat_pairs = pairs_flat.reshape(h, w, 2)
    for y in range(h):
        row = [(int(flat_pairs[y, x, 0]), int(flat_pairs[y, x, 1])) for x in range(w)]
        pairs_rows.append(row)
    return pairs_rows

# --- Fallback (pure Python) mapping (keeps exact composite model) ---
def convert_image_to_pairs_python(img, palette_rgb):
    w, h = img.size
    img_rgb = img.convert("RGB")
    pixels = list(img_rgb.getdata())
    pairs = [[(0,0) for _ in range(w)] for __ in range(h)]
    total = w * h
    start_time = time.time()
    last_update = start_time
    processed = 0
    for y in range(h):
        for x in range(w):
            orig = pixels[y * w + x]
            best_err = None
            best_pair = (0,0)
            for bi, bg in enumerate(palette_rgb):
                bgc = (bg[0] * BG_WEIGHT, bg[1] * BG_WEIGHT, bg[2] * BG_WEIGHT)
                for fi, fg in enumerate(palette_rgb):
                    comp = (bgc[0] + fg[0] * FG_WEIGHT,
                            bgc[1] + fg[1] * FG_WEIGHT,
                            bgc[2] + fg[2] * FG_WEIGHT)
                    err = (comp[0] - orig[0])**2 + (comp[1] - orig[1])**2 + (comp[2] - orig[2])**2
                    if best_err is None or err < best_err:
                        best_err = err
                        best_pair = (bi, fi)
            pairs[y][x] = best_pair
            processed += 1
        now = time.time()
        if now - last_update >= PROGRESS_UPDATE_INTERVAL:
            elapsed = now - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = total - processed
            eta = remaining / rate if rate > 0 else float('inf')
            print_progress(processed, total, eta)
            last_update = now
    print_progress(total, total, 0.0)
    return pairs

# --- Progress printer ---
def print_progress(done, total, eta_seconds):
    remaining = total - done
    pct = (done / total) * 100 if total else 100.0
    if math.isfinite(eta_seconds):
        eta = time.strftime("%H:%M:%S", time.gmtime(max(0, int(eta_seconds))))
    else:
        eta = "??:??:??"
    print(f"\rProcessed: {done}/{total} ({pct:.2f}%)  Remaining: {remaining}  ETA: {eta}", end="", flush=True)
    if done == total:
        print()

# --- Compression helpers (compatible with Lua reader) ---
def compress_pairs_stage1_from_pairs(pair_list, emit_separator=True):
    out_parts = []
    i = 0
    n = len(pair_list)
    while i < n:
        run_char = pair_list[i]
        run_len = 1
        j = i + 1
        while j < n and pair_list[j] == run_char:
            run_len += 1
            j += 1
        if run_len >= 3:
            N = run_len - 2
            a = run_char[0]; b = run_char[1]
            out_parts.append(a); out_parts.append(b)
            out_parts.append(a); out_parts.append(b)
            out_parts.append('x'); out_parts.append(str(N))
            if emit_separator:
                out_parts.append('+')
        else:
            for k in range(run_len):
                out_parts.append(pair_list[i + k][0])
                out_parts.append(pair_list[i + k][1])
        i = j
    return "".join(out_parts)

def compress_singles_stage2_from_string(s, emit_separator=True):
    out_parts = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        run_len = 1
        j = i + 1
        while j < n and s[j] == c:
            run_len += 1
            j += 1
        if run_len >= 3:
            N = run_len - 2
            out_parts.append(c); out_parts.append(c)
            out_parts.append('x'); out_parts.append(str(N))
            if emit_separator:
                out_parts.append('-')
        else:
            out_parts.append(s[i:j])
        i = j
    return "".join(out_parts)

def compress_row_pairs_to_compressed_string(row_pairs):
    stage1 = compress_pairs_stage1_from_pairs(row_pairs, emit_separator=True)
    stage2 = compress_singles_stage2_from_string(stage1, emit_separator=True)
    return stage2 if len(stage2) < len(stage1) else stage1

# --- Main CLI flow ---
def main():
    try:
        ensure_script_cwd()
        png_files = find_png_files()
        image_name = choose_file(png_files)
        if not image_name:
            print("No image selected. Exiting.")
            return
        img = Image.open(image_name)
        default_w, default_h = img.size
        print(f"Original image size: {default_w} x {default_h}")
        new_w, new_h = get_dimensions(default_w, default_h, default_w, default_h)
        if (new_w, new_h) != (default_w, default_h):
            img = img.resize((new_w, new_h), Image.LANCZOS)
            print(f"Resized to: {new_w} x {new_h}")

        # Convert base palette hex to RGB tuples
        base_palette_rgb = [hex_to_rgb(h) for h in BASE_PALETTE_HEX]

        # Optimize palette (k-means) if numpy available
        if np is not None:
            arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
            optimized_palette = optimize_palette_kmeans(arr, base_palette_rgb, k=16)
        else:
            print("NumPy not available: using base palette without optimization.")
            optimized_palette = base_palette_rgb

        # Map pixels to (bg,fg) pairs
        print("Converting pixels to (bg,fg) pairs (this may take a while)...")
        if np is not None:
            pairs = convert_image_to_pairs_vectorized(img, optimized_palette, block_pixels=BLOCK_PIXELS)
        else:
            pairs = convert_image_to_pairs_python(img, optimized_palette)

        # Build output text (compressed)
        out_lines = []
        palette_line = ",".join(["0x" + rgb_to_hex(c) for c in optimized_palette])
        out_lines.append(palette_line)

        h = img.size[1]
        w = img.size[0]
        for y in range(h):
            row_pairs = pairs[y]
            pair_strs = [HEX_DIGITS[bg] + HEX_DIGITS[fg] for (bg, fg) in row_pairs]
            compressed = compress_row_pairs_to_compressed_string(pair_strs)
            out_lines.append(compressed)

        # Write to file
        base_name = os.path.splitext(os.path.basename(image_name))[0]
        out_filename = f"{base_name}.wpft"
        with open(out_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
        print(f"Done. Output written to: {out_filename}")

    except Exception:
        print("failed: " + str(traceback.format_exc()))

if __name__ == "__main__":
    main()
