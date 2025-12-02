from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .downloader import download_from_csv
from .tasks import process_csv

app = typer.Typer(help="Collect m3u8 URLs and download AAC files using a single CLI.")


@app.command()
def collect(
    csv: Path = typer.Argument(..., exists=True, readable=True, help="來源 CSV 檔案"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="輸出 CSV 檔案（預設覆寫來源）"),
    workers: int = typer.Option(2, "--workers", "-w", min=1, show_default=True, help="並行處理線程數"),
    save_interval: int = typer.Option(5, "--save-interval", "-s", min=1, show_default=True, help="每隔多少筆儲存一次"),
    start_from: int = typer.Option(0, "--start-from", "-f", min=0, show_default=True, help="從第幾筆資料開始"),
    max_retries: int = typer.Option(3, "--max-retries", "-r", min=1, show_default=True, help="單筆任務最大重試次數"),
) -> None:
    """批量抓取 m3u8 連結並寫回 CSV。"""
    process_csv(
        str(csv),
        max_workers=workers,
        save_interval=save_interval,
        start_from=start_from,
        max_retries=max_retries,
        output_file=str(output) if output else None,
    )


@app.command()
def download(
    csv: Path = typer.Argument(..., exists=True, readable=True, help="包含 m3u8 欄位的 CSV 檔案"),
    output_dir: Path = typer.Option(Path("output"), "--output-dir", "-o", help="下載輸出目錄"),
    max_threads: Optional[int] = typer.Option(
        None,
        "--max-threads",
        "-t",
        min=1,
        help="下載時使用的最大線程數（預設為 CPU 核心數與 8 的最小值）",
    ),
) -> None:
    """根據 CSV 內容下載 AAC 檔案。"""
    download_from_csv(
        str(csv),
        max_threads=max_threads,
        output_dir=str(output_dir),
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()

