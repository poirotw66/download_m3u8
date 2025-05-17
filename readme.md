這是一個用於批量獲取和下載m3u8媒體文件的Python工具。專案主要用於從特定網站（如Consensus會議網站）獲取m3u8 URL，並將其轉換為AAC音頻文件。

## 功能特點

- 自動從網頁中提取m3u8媒體URL
- 批量處理多個URL並保存到CSV文件
- 支持從m3u8文件下載AAC音頻
- 多線程並行下載，提高效率
- 支持斷點續傳，可從上次中斷的位置繼續處理

## 專案結構

```
download_m3u8/
├── 1_batch_get_url.py       # 批量獲取m3u8 URL的腳本
├── 2_batch_download_aac.py  # 批量下載AAC音頻的腳本
└── src/
    ├── download_m3u8.py     # 核心功能模塊
    └── task_m3u8.csv        # 任務數據文件
```

## 安裝要求

### 依賴套件

- Python 3.6+
- selenium-wire
- pandas
- ffmpeg (用於媒體轉換)

### 安裝步驟

1. 克隆此倉庫到本地：

```bash
git clone https://github.com/yourusername/download_m3u8.git
cd download_m3u8
```

2. 安裝所需的Python套件：

```bash
pip install selenium-wire pandas
```

3. 安裝ffmpeg（用於媒體轉換）：
   - Windows: 下載ffmpeg並將其添加到系統PATH
   - 可從 https://ffmpeg.org/download.html 下載

## 使用方法

### 步驟1：獲取m3u8 URL

運行以下命令來從網頁中提取m3u8 URL：

```bash
python 1_batch_get_url.py
```

這將處理`src/task_m3u8.csv`中的URL，並將找到的m3u8 URL添加到同一文件中。

### 步驟2：下載AAC音頻

運行以下命令來下載AAC音頻：

```bash
python 2_batch_download_aac.py
```

下載的文件將保存在`output`目錄中。

## 參數設置

### 1_batch_get_url.py

- `max_workers`: 最大並行線程數
- `save_interval`: 保存結果的間隔（處理的條目數）
- `start_from`: 處理的起始位置（用於續傳）
- `max_retries`: 最大重試次數

### 2_batch_download_aac.py

- `max_threads`: 最大並行下載線程數

## 注意事項

- 此工具使用Selenium WebDriver，需要安裝相應的瀏覽器驅動
- 下載大量文件時，請注意系統文件描述符限制
- 腳本包含自動清理緩存和增加文件限制的功能

