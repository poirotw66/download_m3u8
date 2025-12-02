from __future__ import annotations

import datetime
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


def _safe_print(lock: threading.Lock, message: str) -> None:
    with lock:
        print(message)


def download_aac_from_m3u8(
    m3u8_url: str,
    output_filename: str,
    *,
    output_dir: str = "output",
    print_lock: Optional[threading.Lock] = None,
) -> Tuple[bool, str]:
    """Download a single m3u8 stream to AAC using ffmpeg."""
    message = f"[*] Downloading: {output_filename}"
    if print_lock:
        _safe_print(print_lock, message)
    else:
        print(message)

    start_time = time.time()
    os.makedirs(output_dir, exist_ok=True)
    safe_filename = output_filename.replace("/", "_").replace("\\", "_").replace(":", "_")
    output_path = Path(output_dir) / f"{safe_filename}.aac"

    cmd = (
        "ffmpeg -y -threads auto "
        "-protocol_whitelist file,http,https,tcp,tls,crypto "
        f'-i "{m3u8_url}" -vn -c:a copy -bsf:a aac_adtstoasc '
        f'-progress pipe:1 "{output_path}"'
    )

    if print_lock:
        _safe_print(print_lock, f"[*] Running command: {cmd}")
    else:
        print(f"[*] Running command: {cmd}")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    elapsed = time.time() - start_time

    if result.returncode == 0:
        msg = f"[*] Download completed: {output_path} (took {elapsed:.2f}s)"
        if print_lock:
            _safe_print(print_lock, msg)
        else:
            print(msg)
        return True, output_filename

    error_header = f"[!] Error downloading {output_filename}:"
    if print_lock:
        _safe_print(print_lock, error_header)
        _safe_print(print_lock, f"[!] {result.stderr}")
    else:
        print(error_header)
        print(f"[!] {result.stderr}")

    with open("error_log.txt", "a", encoding="utf-8") as error_file:
        error_file.write(f"Error downloading {output_filename} at {datetime.datetime.now()}:\n")
        error_file.write(f"{result.stderr}\n\n")

    return False, output_filename


@dataclass
class DownloadStats:
    successful: int = 0
    failed: int = 0


def _parse_csv_rows(csv_file: Path) -> Iterable[Tuple[str, str]]:
    import csv

    with csv_file.open("r", encoding="utf-8") as handle:
        lines = [line for line in handle if not line.strip().startswith("//")]
        reader = csv.DictReader(lines)
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or missing headers.")

        # Normalize the first column name to 'file'
        normalized = ["file" if name and "file" in name else name for name in reader.fieldnames]
        reader.fieldnames = normalized

        if "file" not in reader.fieldnames or "m3u8" not in reader.fieldnames:
            raise ValueError("CSV must contain 'file' and 'm3u8' columns.")

        for row in reader:
            yield row.get("file", ""), row.get("m3u8", "")


def download_from_csv(
    csv_file: str,
    *,
    max_threads: Optional[int] = None,
    output_dir: str = "output",
) -> DownloadStats:
    """Download all m3u8 entries referenced in the provided CSV file."""
    csv_path = Path(csv_file)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    max_threads = max_threads or min(os.cpu_count() or 1, 8)
    print(f"[*] Reading CSV file: {csv_file}")
    print(f"[*] Using {max_threads} parallel download threads")

    stats = DownloadStats()
    tasks: "queue.Queue[Optional[Tuple[str, str]]]" = queue.Queue()
    results: List[Tuple[bool, str]] = []
    print_lock = threading.Lock()

    for file_name, m3u8_url in _parse_csv_rows(csv_path):
        if not m3u8_url:
            print(f"[!] No m3u8 URL provided for {file_name}, skipping.")
            stats.failed += 1
            continue
        tasks.put((file_name, m3u8_url))

    def worker() -> None:
        while True:
            try:
                task = tasks.get(block=False)
            except queue.Empty:
                return
            try:
                if task is None:
                    return
                file_name, m3u8_url = task
                success, filename = download_aac_from_m3u8(
                    m3u8_url,
                    file_name,
                    output_dir=output_dir,
                    print_lock=print_lock,
                )
                results.append((success, filename))
            finally:
                tasks.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max_threads)]
    for thread in threads:
        thread.start()

    tasks.join()

    for thread in threads:
        thread.join()

    for success, _filename in results:
        if success:
            stats.successful += 1
        else:
            stats.failed += 1

    print("\n" + "=" * 50)
    print("[*] Download Summary:")
    print(f"[*] Total files processed: {stats.successful + stats.failed}")
    print(f"[*] Successfully downloaded: {stats.successful}")
    print(f"[*] Failed downloads: {stats.failed}")
    print("=" * 50)
    return stats

