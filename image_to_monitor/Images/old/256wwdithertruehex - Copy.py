#!/usr/bin/env python3
"""
High-fidelity, optimized image -> 256-combination dither exporter.

FINAL FORMAT:
-----------------------------------------
TEXT:
0xRRGGBB,0xRRGGBB,...,0xRRGGBB
FFFFFFFFFF


BINARY:
[value][count][value][count]...[0A]
[value][count][value][count]...[0A]
...
-----------------------------------------
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
PROGRESS_UPDATE_INTERVAL = 0.5
BLOCK_PIXELS = 100_000

# Base palette (hex) in required fixed order (index 0..f)
BASE_PALETTE_HEX = [
    "F0F0F0", "F2B233", "E57FD8", "99B2F2",
    "DEDE6C", "7FCC19", "F2B2CC", "4C4C4C",
    "999999", "4C99B2", "B266E5", "3366CC",
    "7F664C", "57A64E", "CC4C4C", "111111"
]

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
    
    w_str = ""
    h_str = ""
    dim_file = "dimensions.txt"
    
    # Read from the file instead of prompting for inputs
    if os.path.exists(dim_file):
        with open(dim_file, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            if len(lines) >= 1:
                w_str = lines[0] # Maps to Monitor Height
            if len(lines) >= 2:
                h_str = lines[1] # Maps to Monitor Width
    else:
        print(f"'{dim_file}' not found. Using default dimensions.")
        # Auto-create the file to make it easy for the user next time
        try:
            with open(dim_file, "w") as f:
                f.write(f"{default_w}\n{default_h}\n")
        except Exception:
            pass

    # Your original scaling logic
    if img_w > img_h:
        w_str = w_str
        h_str = ""
    else:
        w_str = ""
        h_str = h_str
        
    try:
        if not w_str and not h_str:
            return int(default_w), int(default_h)
        if w_str and not h_str:
            w = int(w_str)
            scale = w / img_w
            h = int(round(img_h * scale / ASPECT_RATIO))
            return w, max(1, h)
        if h_str and not w_str:
            h = int(h_str)
            scale = h / img_h
            w = int(round(img_w * scale * ASPECT_RATIO))
            return max(1, w), h
        
        w = int(w_str) if w_str else int(default_w)
        h = int(h_str) if h_str else int(default_h)
        return max(1, w), max(1, h)
        
    except ValueError:
        print(f"Invalid integer found in {dim_file}. Falling back to default dimensions.")
        return int(default_w), int(default_h)

# --- Color conversions (NumPy vectorized) ---
def srgb_to_linear_np(arr):
    a = 0.055
    low_mask = arr <= 0.04045
    out = np.empty_like(arr, dtype=np.float32)
    out[low_mask] = arr[low_mask] / 12.92
    out[~low_mask] = ((arr[~low_mask] + a) / (1 + a)) ** 2.4
    return out

def linear_to_xyz_np(lin):
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
    flat = lin.reshape(-1, 3)
    xyz = flat.dot(M.T)
    return xyz.reshape(lin.shape)

def xyz_to_lab_np(xyz):
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
    return np.stack([L, a, b], axis=-1).astype(np.float32)

def rgb8_to_lab_np(rgb8):
    arr = rgb8.astype(np.float32) / 255.0
    lin = srgb_to_linear_np(arr)
    xyz = linear_to_xyz_np(lin)
    return xyz_to_lab_np(xyz)

# --- Palette optimization ---
def optimize_palette_kmeans(img_rgb_array, base_palette_rgb, k=16, samples=KMEANS_SAMPLES, iters=KMEANS_ITERS):
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
                new_centroids[i] = centroids[i]
        if np.linalg.norm(new_centroids - centroids) < 0.5:
            break
        centroids = new_centroids

    return [tuple(map(int, np.clip(c, 0, 255))) for c in centroids.tolist()]

# --- Vectorized mapping ---
def convert_image_to_pairs_vectorized(img, palette_rgb, block_pixels=BLOCK_PIXELS):
    w, h = img.size
    arr8 = np.asarray(img.convert("RGB"), dtype=np.uint8)
    flat8 = arr8.reshape(-1, 3)

    pal8 = np.array(palette_rgb, dtype=np.uint8)
    pal_lin = srgb_to_linear_np(pal8.astype(np.float32) / 255.0)

    comps_lin = np.empty((256, 3), dtype=np.float32)
    idx = 0
    for bi in range(16):
        for fi in range(16):
            comps_lin[idx] = pal_lin[bi] * BG_WEIGHT + pal_lin[fi] * FG_WEIGHT
            idx += 1

    comps_lab = xyz_to_lab_np(linear_to_xyz_np(comps_lin))

    total = flat8.shape[0]
    pairs_flat = np.empty((total, 2), dtype=np.uint8)

    start = 0
    last_update = time.time()
    t0 = last_update
    processed = 0

    while start < total:
        end = min(start + block_pixels, total)
        block8 = flat8[start:end].astype(np.float32) / 255.0
        block_lab = xyz_to_lab_np(linear_to_xyz_np(srgb_to_linear_np(block8)))

        diff = block_lab[:, None, :] - comps_lab[None, :, :]
        d2 = np.einsum('ijk,ijk->ij', diff, diff)
        idxs = np.argmin(d2, axis=1).astype(np.int32)

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

    flat_pairs = pairs_flat.reshape(h, w, 2)
    return [[(int(flat_pairs[y, x, 0]), int(flat_pairs[y, x, 1])) for x in range(w)] for y in range(h)]

# --- Fallback mapping ---
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
                            bgc[2] * FG_WEIGHT)
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

# --- NEW: Binary RLE encoder ---
def rle_encode_row(row_pairs):
    out = bytearray()
    n = len(row_pairs)
    i = 0
    while i < n:
        bg, fg = row_pairs[i]
        value = (bg << 4) | fg

        run_len = 1
        j = i + 1
        while j < n and row_pairs[j] == row_pairs[i] and run_len < 255:
            run_len += 1
            j += 1

        out.append(value)
        out.append(run_len)

        i = j
    return bytes(out)

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

        base_palette_rgb = [hex_to_rgb(h) for h in BASE_PALETTE_HEX]

        if np is not None:
            arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
            optimized_palette = optimize_palette_kmeans(arr, base_palette_rgb, k=16)
        else:
            optimized_palette = base_palette_rgb

        print("Converting pixels to (bg,fg) pairs...")
        if np is not None:
            pairs = convert_image_to_pairs_vectorized(img, optimized_palette, block_pixels=BLOCK_PIXELS)
        else:
            pairs = convert_image_to_pairs_python(img, optimized_palette)

        # --- Write output ---
        base_name = os.path.splitext(os.path.basename(image_name))[0]
        out_filename = f"{base_name}.wpft"

        with open(out_filename, "wb") as f:
            # 1. Palette line (TEXT)
            palette_line = ",".join(["0x" + rgb_to_hex(c) for c in optimized_palette])
            f.write((palette_line + "\n").encode("utf-8"))

            # 2. Marker line (TEXT)
            f.write(b"FFFFFFFFFF\n")

            # 3. Three newline bytes
            f.write(b"\n\n\n")

            # 4. Binary RLE rows
            h = img.size[1]
            for y in range(h):
                encoded = rle_encode_row(pairs[y])
                f.write(encoded)
                f.write(b"\xFF\x00")  # safe row terminator


        print(f"Done. Output written to: {out_filename}")

    except Exception:
        print("failed: " + str(traceback.format_exc()))

if __name__ == "__main__":
    main()
