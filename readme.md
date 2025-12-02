這是一個用於批量獲取和下載 m3u8 媒體文件的 Python 工具包。新版專案提供可擴充的 `download-m3u8` CLI，負責從會議頁面取得 m3u8 URL，並透過 ffmpeg 批次轉換成 AAC 音訊。

## 功能特點

- 自動從網頁中提取m3u8媒體URL
- 批量處理多個URL並保存到CSV文件
- 支持從m3u8文件下載AAC音頻
- 多線程並行下載，提高效率
- 支持斷點續傳，可從上次中斷的位置繼續處理

## 專案結構

```
download_m3u8/
├── pyproject.toml                 # 套件與 CLI 設定
├── 1_batch_get_url.py             # 舊版腳本 -> 轉呼叫新模組
├── 2_batch_download_aac.py        # 舊版腳本 -> 轉呼叫新模組
└── src/
    └── download_m3u8/
        ├── __init__.py            # 導出高階 API
        ├── cli.py                 # Typer CLI
        ├── collector.py           # Selenium 抓取邏輯
        ├── downloader.py          # ffmpeg 下載器
        └── tasks.py               # CSV 任務控制
```

## 安裝要求

1. 依賴套件
   - Python 3.10+
   - `ffmpeg`（需自行安裝並加入 PATH）
   - Python 套件：`selenium`, `selenium-wire`, `pandas`, `typer`

2. 安裝步驟

```bash
git clone https://github.com/yourusername/download_m3u8.git
cd download_m3u8
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

3. 安裝 ffmpeg：可至 <https://ffmpeg.org/download.html> 下載並加入 PATH。

## 使用方法

### CLI：`download-m3u8 collect`

從 CSV 讀取 session URL，抓取 m3u8 並輸出到 CSV。

```bash
download-m3u8 collect src/task_m3u8.csv \
  --workers 2 \
  --save-interval 5 \
  --start-from 0 \
  --max-retries 3 \
  --output task_m3u8.csv
```

### CLI：`download-m3u8 download`

根據 CSV 內容呼叫 ffmpeg 批量下載 AAC。

```bash
download-m3u8 download task_m3u8.csv \
  --output-dir output \
  --max-threads 4
```

> 舊版 `python 1_batch_get_url.py` 與 `python 2_batch_download_aac.py` 仍可使用，它們現在只是對新模組的薄包裝。

## 參數設置

- `collect`：
  - `--workers`：最大並行線程數
  - `--save-interval`：每處理幾筆立即儲存
  - `--start-from`：從第幾筆開始（續傳用途）
  - `--max-retries`：單筆重試次數
  - `--output`：結果輸出檔案；若未提供則覆寫來源 CSV
- `download`：
  - `--max-threads`：最大下載線程數
  - `--output-dir`：AAC 輸出路徑

## 注意事項

- 此工具使用Selenium WebDriver，需要安裝相應的瀏覽器驅動
- 下載大量文件時，請注意系統文件描述符限制
- CLI 會自動清理 Selenium Wire 緩存並提升文件描述符上限，但仍建議自行監控系統限制
- 若運行於伺服器環境，記得預先安裝 Chrome/Chromedriver 或使用對應容器映像

