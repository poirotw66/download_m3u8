from download_m3u8.downloader import download_from_csv


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="從 CSV 批量下載 AAC 檔案（使用 download_m3u8 套件）")
    parser.add_argument("--csv", type=str, default="consensus_test.csv", help="CSV 文件路徑")
    parser.add_argument("--output-dir", type=str, default="output", help="下載輸出目錄")
    parser.add_argument("--threads", type=int, default=None, help="最大下載線程數（預設自動）")
    args = parser.parse_args()

    download_from_csv(
        args.csv,
        max_threads=args.threads,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()

