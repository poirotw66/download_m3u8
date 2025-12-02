from __future__ import annotations

import concurrent.futures
import datetime
import gc
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from .collector import clear_seleniumwire_cache, get_m3u8_url, increase_file_limit


def process_csv(
    csv_file: str,
    *,
    max_workers: int = 2,
    save_interval: int = 5,
    start_from: int = 0,
    max_retries: int = 3,
    output_file: Optional[str] = None,
) -> None:
    """
    Read a CSV containing URLs, fetch m3u8 links for each entry, and persist the result.
    """

    source_path = Path(csv_file)
    if not source_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    output_path = Path(output_file or source_path)
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".checkpoint")

    print(f"[*] 开始处理 CSV 文件: {source_path}")
    print(f"[*] 输出文件: {output_path}")
    print(f"[*] 设置: 最大并发數={max_workers}, 保存間隔={save_interval}, 起始位置={start_from}")
    print(f"[*] 开始时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    increase_file_limit()
    clear_seleniumwire_cache()

    if checkpoint_path.exists() and start_from == 0:
        try:
            start_from = int(checkpoint_path.read_text(encoding="utf-8").strip())
            print(f"[*] 从上次中断点继续处理: 第 {start_from} 笔")
        except Exception as exc:
            print(f"[!] 读取断点文件时发生错误: {exc}")

    df = pd.read_csv(source_path, encoding="utf-8")
    if "m3u8" not in df.columns:
        df["m3u8"] = ""

    print(f"[*] CSV 欄位名稱: {list(df.columns)}")
    print(f"[*] 读取到 {len(df)} 筆資料")

    tasks = []
    for idx, row in df.iloc[start_from:].iterrows():
        url = str(row.get("url", "")).strip()
        if not url:
            print(f"[!] 第 {idx+1} 筆資料缺少 URL，跳過")
            continue
        if not pd.isna(row.get("m3u8")) and str(row.get("m3u8")):
            print(f"[*] 第 {idx+1} 筆資料已有 m3u8 数据，跳過")
            continue
        file_name = row.get(df.columns[0], f"項目 {idx+1}")
        tasks.append((idx, url, file_name))

    if not tasks:
        print("[*] 沒有需要處理的任務或全部已完成")
        df.to_csv(output_path, index=False, encoding="utf-8")
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        return

    print(f"[*] 待處理任務數: {len(tasks)}")
    processed_count = 0
    batch_size = 10

    for batch_start in range(0, len(tasks), batch_size):
        batch_end = min(batch_start + batch_size, len(tasks))
        current_batch = tasks[batch_start:batch_end]
        print(f"[*] 開始處理第 {batch_start+1} 到 {batch_end} 筆任務 (共 {len(tasks)} 筆)")

        clear_seleniumwire_cache()
        gc.collect()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(_process_url_safe, url, file_name, idx, len(df)): idx for idx, url, file_name in current_batch
            }

            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                retry = 0
                result = ""
                while retry < max_retries:
                    try:
                        result = future.result()
                        break
                    except Exception as exc:
                        retry += 1
                        print(f"[!] 任務 {idx+1} 執行失敗 (嘗試 {retry}/{max_retries}): {exc}")
                        if retry < max_retries:
                            time.sleep(2)
                df.at[idx, "m3u8"] = result
                processed_count += 1

                checkpoint_path.write_text(str(idx + 1), encoding="utf-8")
                df.to_csv(output_path, index=False, encoding="utf-8")
                print(f"[*] 已处理 {processed_count}/{len(tasks)} 筆資料，已儲存到 {output_path}")

        batch_progress = (batch_end / len(tasks)) * 100
        print(f"[*] 已完成 {batch_end}/{len(tasks)} 筆任務 ({batch_progress:.1f}%)")
        print(f"[*] 休息 2 秒后继续下一批...")
        time.sleep(2)

    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"[*] 全部處理完成，最終結果已儲存至 {output_path}")
    if checkpoint_path.exists():
        checkpoint_path.unlink()
    print(f"[*] 處理完成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def _process_url_safe(url: str, file_name: str, index: int, total: int) -> str:
    print(f"[*] 处理第 {index+1}/{total} 筆資料: {file_name}")
    print(f"[*] URL: {url}")
    try:
        m3u8_url = get_m3u8_url(url)
        if m3u8_url:
            print(f"[*] 成功取得 m3u8: {m3u8_url}")
            return m3u8_url
        print(f"[!] 無法取得 m3u8")
        return ""
    except Exception as exc:
        print(f"[!] 处理 URL 時發生錯誤: {exc}")
        return ""
    finally:
        gc.collect()

