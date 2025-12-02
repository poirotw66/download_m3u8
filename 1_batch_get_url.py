from download_m3u8.tasks import process_csv


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="批量獲取 m3u8 連結（使用 download_m3u8 套件）")
    parser.add_argument("--csv", type=str, default="consensus_test.csv", help="CSV 文件路徑")
    parser.add_argument("--workers", type=int, default=2, help="並行處理的線程數")
    parser.add_argument("--save", type=int, default=5, help="每處理多少條數據保存一次")
    parser.add_argument("--start", type=int, default=0, help="從第幾條數據開始處理")
    parser.add_argument("--retries", type=int, default=3, help="重試次數")
    parser.add_argument("--output", type=str, default="task_m3u8.csv", help="輸出 CSV 文件名")
    args = parser.parse_args()

    process_csv(
        args.csv,
        max_workers=args.workers,
        save_interval=args.save,
        start_from=args.start,
        max_retries=args.retries,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
