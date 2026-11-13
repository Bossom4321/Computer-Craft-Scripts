#!/usr/bin/env python3

import argparse
import logging
import logging.handlers
import sys
import traceback
import concurrent.futures
import re
from pathlib import Path
import tempfile

import dfpwm
import soundfile as sf
import numpy as np
from scipy.signal import resample_poly, butter, filtfilt
import yt_dlp
from tqdm import tqdm

LOG_FILENAME = "dfpwm_convert.log"
logger = logging.getLogger("dfpwm_converter")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
fh.setFormatter(formatter)
logger.addHandler(fh)

def sanitize_filename(name: str) -> str:
    """
    Extracts up to the first three words, removing spaces and non-alphanumeric characters.
    """
    # Find all sequences of alphanumeric characters
    words = re.findall(r'[a-zA-Z0-9]+', name)
    # Take up to the first 3 words and join them with no spaces
    return "".join(words[:3])

def high_quality_resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return data.astype(np.float32)

    gcd = np.gcd(orig_sr, target_sr)
    up = target_sr // gcd
    down = orig_sr // gcd

    return resample_poly(data, up, down).astype(np.float32)

def lowpass_filter(data: np.ndarray, sr: int, cutoff: float = 8000.0) -> np.ndarray:
    b, a = butter(6, cutoff / (sr / 2), btype="low")
    return filtfilt(b, a, data).astype(np.float32)

def read_audio(path: Path):
    try:
        data, sr = sf.read(str(path), dtype="float32")
    except Exception as e:
        logger.debug("soundfile failed to read %s: %s", path, e)
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(str(path))
            seg = seg.set_frame_rate(dfpwm.SAMPLE_RATE).set_channels(1)
            samples = seg.get_array_of_samples()

            if seg.sample_width == 1:
                arr = np.frombuffer(samples, dtype=np.uint8).astype(np.int16) - 128
            elif seg.sample_width == 2:
                arr = np.frombuffer(samples, dtype=np.int16)
            elif seg.sample_width == 4:
                arr = (np.frombuffer(samples, dtype=np.int32) >> 16).astype(np.int16)
            else:
                arr = np.array(samples)

            data = arr.astype("float32") / 32768.0
            sr = dfpwm.SAMPLE_RATE
        except Exception as e2:
            raise RuntimeError(f"Failed to read audio with soundfile and pydub: {e2}") from e

    if getattr(data, "ndim", 0) > 1:
        data = np.mean(data, axis=1)

    if sr != dfpwm.SAMPLE_RATE:
        try:
            data = dfpwm.resample(data, sr)
        except Exception:
            data = high_quality_resample(data, sr, dfpwm.SAMPLE_RATE)
        sr = dfpwm.SAMPLE_RATE

    data = np.asarray(data, dtype=np.float32)
    data = np.clip(data, -1.0, 1.0)

    return data, sr

def preprocess_audio(data: np.ndarray, sr: int) -> np.ndarray:
    if data.size == 0:
        return data.astype(np.float64)

    data = data - np.mean(data)

    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak

    data = lowpass_filter(data, sr)

    return data.astype(np.float64)

def convert_file(in_path: Path, out_path: Path):
    try:
        data, sr = read_audio(in_path)
    except Exception as e:
        raise RuntimeError(f"Error reading {in_path}: {e}") from e

    try:
        data = preprocess_audio(data, sr)
    except Exception as e:
        raise RuntimeError(f"Preprocessing failed for {in_path}: {e}") from e

    try:
        encoded = dfpwm.compressor(data)
    except Exception as e:
        raise RuntimeError(f"DFPWM encoding failed for {in_path}: {e}") from e

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(encoded)
    except Exception as e:
        raise RuntimeError(f"Failed to write output {out_path}: {e}") from e

def process_file_task(p: Path, out_file: Path, continue_on_error: bool):
    try:
        convert_file(p, out_file)
    except Exception as e:
        logger.error("Error converting %s: %s", p, e)
        logger.debug("Traceback:\n%s", traceback.format_exc())
        if not continue_on_error:
            raise

def process_txt_input(txt_path: Path, staging_dir: Path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        return

    ydl_opts = {
        'ffmpeg_location': r'C:\Users\bosso\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-essentials_build\bin', 
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': str(staging_dir / '%(title)s.%(ext)s'),
        'quiet': False
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)

def convert_folder(src: Path, dst: Path, recursive: bool = False, continue_on_error: bool = False):
    dst.mkdir(parents=True, exist_ok=True)
    pattern = "**/*" if recursive else "*"

    # 1. Find standard audio files
    files = sorted([p for p in src.glob(pattern)
                    if p.is_file() and p.suffix.lower() in (".wav", ".mp3")])

    # 2. Find .txt files
    txt_files = sorted([p for p in src.glob(pattern)
                        if p.is_file() and p.suffix.lower() == ".txt"])

    temp_dir_obj = None

    try:
        # 3. If .txt files exist, process them and add downloaded files to the batch
        if txt_files:
            temp_dir_obj = tempfile.TemporaryDirectory()
            staging_path = Path(temp_dir_obj.name)
            
            for txt_file in txt_files:
                logger.info("Reading YouTube links from %s...", txt_file.name)
                process_txt_input(txt_file, staging_path)
            
            # Add the freshly downloaded files to our list
            downloaded_files = sorted([p for p in staging_path.glob("*")
                                       if p.is_file() and p.suffix.lower() in (".wav", ".mp3")])
            files.extend(downloaded_files)

        if not files:
            logger.warning("No .wav, .mp3, or valid .txt files found in %s", src)
            return

        # 4. Pre-calculate output paths to sanitize names and avoid naming collisions
        tasks = []
        used_names = set()
        for p in files:
            new_stem = sanitize_filename(p.stem)
            if not new_stem:
                new_stem = "audio_unknown"
                
            out_name = new_stem
            counter = 1
            # Resolve collisions if multiple inputs generate the exact same three words
            while out_name in used_names:
                out_name = f"{new_stem}{counter}"
                counter += 1
                
            used_names.add(out_name)
            out_file = dst / f"{out_name}.dfpwm"
            tasks.append((p, out_file))

        # 5. Convert everything
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = [executor.submit(process_file_task, src_p, dest_p, continue_on_error) for src_p, dest_p in tasks]
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="converting files", unit="file"):
                try:
                    future.result()
                except Exception:
                    if not continue_on_error:
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise
    finally:
        # Always clean up the temporary directory when finished
        if temp_dir_obj:
            temp_dir_obj.cleanup()

def parse_args():
    ap = argparse.ArgumentParser(description="Convert WAV/MP3 folder or YouTube TXT to Computercraft DFPWM files")
    ap.add_argument("src", type=Path, help="Source folder containing .wav/.mp3/.txt files")
    ap.add_argument("dst", type=Path, help="Output folder for .dfpwm files")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    ap.add_argument("--continue-on-error", action="store_true", help="Skip files that error and continue")
    ap.add_argument("--debug", action="store_true", help="Enable debug logging to console")
    return ap.parse_args()

def main():
    args = parse_args()
    ch.setLevel(logging.DEBUG if args.debug else logging.INFO)
    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        # Pass the folder straight to convert_folder
        if args.src.is_file() and args.src.suffix.lower() == ".txt":
            # Just in case you still point it directly at a text file
            convert_folder(args.src.parent, args.dst, args.recursive, args.continue_on_error)
        else:
            convert_folder(args.src, args.dst, args.recursive, args.continue_on_error)
    except Exception as e:
        logger.error("Conversion aborted: %s", e)
        if args.debug:
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()