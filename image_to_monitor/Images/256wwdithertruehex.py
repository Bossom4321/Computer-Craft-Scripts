#!/usr/bin/env python3
"""
High-fidelity, optimized image -> 256-combination dither exporter.
Auto-installs required libraries, strictly uses vectorized operations,
and supports batch processing of all major image formats.

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

import os
import sys
import math
import time
import traceback
import subprocess
from itertools import groupby

# --- Auto-Dependency Installer ---
def install_package(package_name):
    print(f"Missing library '{package_name}'. Attempting to install...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"Successfully installed {package_name}.")
    except Exception as e:
        print(f"Failed to install {package_name}. Please run: pip install {package_name}")
        sys.exit(1)

try:
    from PIL import Image
except ImportError:
    install_package("Pillow")
    from PIL import Image

try:
    import numpy as np
except ImportError:
    install_package("numpy")
    import numpy as np


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

# Supported formats recognized by Pillow
SUPPORTED_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.bmp', '.gif', 
    '.tiff', '.tif', '.webp', '.avif', '.blp', '.dds'
)


# --- Utilities ---
def hex_to_rgb(h):
    h = h.strip().lstrip("0x").lstrip("0X")
    if len(h) == 3:
        h = ''.join([c*2 for c in h])
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return "{:02X}{:02X}{:02X}".format(*(int(round(max(0, min(255, v)))) for v in rgb))

def ensure_script_cwd():
    script_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    os.chdir(script_dir)

def choose_files():
    image_files = [f for f in os.listdir('.') if f.lower().endswith(SUPPORTED_EXTENSIONS)]
    if not image_files:
        print("No supported image files found in script directory.")
        return []
    if len(image_files) == 1:
        return [image_files[0]]
        
    print(f"\nFound {len(image_files)} image files:")
    for i, name in enumerate(image_files, 1):
        print(f"  {i}. {name}")
        
    while True:
        convert_all = input(f"\nDo you want to convert all {len(image_files)} images? (y/n): ").strip().lower()
        if convert_all in ['y', 'yes']:
            return image_files
        elif convert_all in ['n', 'no']:
            break
        print("Invalid input. Please enter 'y' or 'n'.")
        
    while True:
        choice = input(f"\nChoose a single file number (1-{len(image_files)}) or type filename: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(image_files):
            return [image_files[int(choice) - 1]]
        if choice in image_files:
            return [choice]
        print("Invalid selection, try again.")

def get_dimensions(default_w, default_h, img_w, img_h):
    ASPECT_RATIO = 9/6
    dim_file = "dimensions.txt"
    w_str, h_str = "", ""
    
    if os.path.exists(dim_file):
        with open(dim_file, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            w_str = lines[0] if len(lines) >= 1 else ""
            h_str = lines[1] if len(lines) >= 2 else ""
    else:
        print(f"'{dim_file}' not found. Using default dimensions.")
        try:
            with open(dim_file, "w") as f:
                f.write(f"{default_w}\n{default_h}\n")
        except IOError:
            pass

    # Clear constraints based on dominant image orientation
    if img_w > img_h:
        h_str = ""
    else:
        w_str = ""
        
    try:
        if w_str:
            w = int(w_str)
            return w, max(1, int(round(img_h * (w / img_w) / ASPECT_RATIO)))
        if h_str:
            h = int(h_str)
            return max(1, int(round(img_w * (h / img_h) * ASPECT_RATIO))), h
        return int(default_w), int(default_h)
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
    return lin.reshape(-1, 3).dot(M.T).reshape(lin.shape)

def xyz_to_lab_np(xyz):
    xr, yr, zr = 0.95047, 1.00000, 1.08883
    x, y, z = xyz[..., 0] / xr, xyz[..., 1] / yr, xyz[..., 2] / zr
    eps, kappa = 0.008856, 903.3

    def f(t):
        mask = t > eps
        out = np.empty_like(t, dtype=np.float32)
        out[mask] = np.cbrt(t[mask])
        out[~mask] = (kappa * t[~mask] + 16.0) / 116.0
        return out

    fx, fy, fz = f(x), f(y), f(z)
    L = (116.0 * fy) - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.stack([L, a, b], axis=-1).astype(np.float32)

def rgb8_to_lab_np(rgb8):
    return xyz_to_lab_np(linear_to_xyz_np(srgb_to_linear_np(rgb8.astype(np.float32) / 255.0)))


# --- Palette optimization ---
def optimize_palette_kmeans(img_rgb_array, base_palette_rgb, k=16, samples=KMEANS_SAMPLES, iters=KMEANS_ITERS):
    h, w, _ = img_rgb_array.shape
    total = h * w
    flat = img_rgb_array.reshape(-1, 3).astype(np.float32)
    
    if total <= samples:
        sample_pixels = flat
    else:
        rng = np.random.default_rng(seed=42)
        sample_pixels = flat[rng.choice(total, size=samples, replace=False)]

    centroids = np.array(base_palette_rgb, dtype=np.float32)[:k].copy()

    for _ in range(iters):
        dists = np.sum((sample_pixels[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
        labels = np.argmin(dists, axis=1)
        new_centroids = np.zeros_like(centroids)
        for i in range(k):
            mask = labels == i
            new_centroids[i] = sample_pixels[mask].mean(axis=0) if np.any(mask) else centroids[i]
            
        if np.linalg.norm(new_centroids - centroids) < 0.5:
            break
        centroids = new_centroids

    return [tuple(map(int, np.clip(c, 0, 255))) for c in centroids.tolist()]


# --- Vectorized mapping ---
def convert_image_to_pairs_vectorized(img, palette_rgb, block_pixels=BLOCK_PIXELS):
    w, h = img.size
    
    # Ensure image is RGB to avoid shape dimension mismatch on grayscale or RGBA images
    img_rgb = img.convert("RGB")
    arr8 = np.asarray(img_rgb, dtype=np.uint8)
    flat8 = arr8.reshape(-1, 3)

    pal_lin = srgb_to_linear_np(np.array(palette_rgb, dtype=np.float32) / 255.0)
    
    # Precompute 256 background/foreground combinations
    comps_lin = np.empty((256, 3), dtype=np.float32)
    for bi in range(16):
        for fi in range(16):
            comps_lin[bi * 16 + fi] = pal_lin[bi] * BG_WEIGHT + pal_lin[fi] * FG_WEIGHT

    comps_lab = xyz_to_lab_np(linear_to_xyz_np(comps_lin))
    total = flat8.shape[0]
    pairs_flat = np.empty((total, 2), dtype=np.uint8)

    start = 0
    t0 = last_update = time.time()
    processed = 0

    while start < total:
        end = min(start + block_pixels, total)
        block_lab = rgb8_to_lab_np(flat8[start:end])

        diff = block_lab[:, None, :] - comps_lab[None, :, :]
        idxs = np.argmin(np.einsum('ijk,ijk->ij', diff, diff), axis=1).astype(np.int32)

        pairs_flat[start:end, 0] = (idxs // 16).astype(np.uint8)
        pairs_flat[start:end, 1] = (idxs % 16).astype(np.uint8)

        processed += (end - start)
        now = time.time()
        if now - last_update >= PROGRESS_UPDATE_INTERVAL:
            elapsed = now - t0
            rate = processed / elapsed if elapsed > 0 else 0
            print_progress(processed, total, (total - processed) / rate if rate > 0 else float('inf'))
            last_update = now
        start = end

    print_progress(total, total, 0.0)
    flat_pairs = pairs_flat.reshape(h, w, 2)
    return [[(int(flat_pairs[y, x, 0]), int(flat_pairs[y, x, 1])) for x in range(w)] for y in range(h)]


# --- Progress printer ---
def print_progress(done, total, eta_seconds):
    pct = (done / total) * 100 if total else 100.0
    eta = time.strftime("%H:%M:%S", time.gmtime(max(0, int(eta_seconds)))) if math.isfinite(eta_seconds) else "??:??:??"
    print(f"\rProcessed: {done}/{total} ({pct:.2f}%)  Remaining: {total - done}  ETA: {eta}", end="", flush=True)
    if done == total:
        print()


# --- Binary RLE encoder ---
def rle_encode_row(row_pairs):
    out = bytearray()
    for pair, group in groupby(row_pairs):
        value = (pair[0] << 4) | pair[1]
        count = sum(1 for _ in group)
        while count > 0:
            chunk = min(count, 255)
            out.extend([value, chunk])
            count -= chunk
    return bytes(out)


# --- Main CLI flow ---
def main():
    try:
        ensure_script_cwd()
        image_names = choose_files()
        
        if not image_names:
            print("No image selected. Exiting.")
            return

        for index, image_name in enumerate(image_names):
            if len(image_names) > 1:
                print(f"\n[{index + 1}/{len(image_names)}] Processing: {image_name}")
                print("-" * 40)
            else:
                print(f"\nProcessing: {image_name}")

            img = Image.open(image_name)
            default_w, default_h = img.size
            print(f"Original image size: {default_w} x {default_h}")
            new_w, new_h = get_dimensions(default_w, default_h, default_w, default_h)

            if (new_w, new_h) != (default_w, default_h):
                img = img.resize((new_w, new_h), Image.LANCZOS)
                print(f"Resized to: {new_w} x {new_h}")

            base_palette_rgb = [hex_to_rgb(h) for h in BASE_PALETTE_HEX]

            # Ensure Image is RGB prior to array conversion to guarantee shape depth of 3
            arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
            optimized_palette = optimize_palette_kmeans(arr, base_palette_rgb, k=16)

            print("Converting pixels to (bg,fg) pairs...")
            pairs = convert_image_to_pairs_vectorized(img, optimized_palette, block_pixels=BLOCK_PIXELS)

            # --- Write output ---
            base_name = os.path.splitext(os.path.basename(image_name))[0]
            out_filename = f"{base_name}.wpft"

            with open(out_filename, "wb") as f:
                palette_line = ",".join(["0x" + rgb_to_hex(c) for c in optimized_palette])
                f.write((palette_line + "\n").encode("utf-8"))
                f.write(b"FFFFFFFFFF\n")
                f.write(b"\n\n\n")

                for row in pairs:
                    f.write(rle_encode_row(row))
                    f.write(b"\xFF\x00")

            print(f"Done. Output written to: {out_filename}")

        if len(image_names) > 1:
            print("\nAll images processed successfully!")

    except Exception:
        print("failed: " + str(traceback.format_exc()))

if __name__ == "__main__":
    main()