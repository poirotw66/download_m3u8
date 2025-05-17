import time
import datetime
import os
import concurrent.futures
import gc
import pandas as pd
from src.download_m3u8 import get_m3u8_url, clear_seleniumwire_cache, increase_file_limit

def process_url(url, file_name, index, total):
    """
    Process a single URL and obtain m3u8 link
    """
    print(f"[*] 处理第 {index+1}/{total} 筆資料: {file_name}")
    print(f"[*] URL: {url}")
    
    try:
        m3u8_url = get_m3u8_url(url)
        if m3u8_url:
            print(f"[*] 成功取得 m3u8: {m3u8_url}")
            return m3u8_url
        else:
            print(f"[!] 無法取得 m3u8")
            return ""
    except Exception as e:
        print(f"[!] 处理 URL 時发生错误: {e}")
        return ""
    finally:
        gc.collect()

def process_csv(csv_file, max_workers=2, save_interval=5, start_from=0, max_retries=3, output_file="task_m3u8.csv"):
    """
    Read CSV file, get m3u8 URLs for each entry, and update the CSV file
    
    Parameters:
    - csv_file: Path to the CSV file
    - max_workers: Maximum number of parallel threads
    - save_interval: How often to save results (number of entries)
    - start_from: Starting position for processing (for resuming)
    - max_retries: Maximum retry attempts on error
    - output_file: Output CSV file name
    """
    print(f"[*] 开始处理 CSV 文件: {csv_file}")
    print(f"[*] 开始时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] 设置: 最大并发数={max_workers}, 保存间隔={save_interval}, 起始位置={start_from}")
    print(f"[*] 输出文件: {output_file}")
    
    increase_file_limit()
    
    clear_seleniumwire_cache()
    
    # 使用输出文件名作为检查点文件名
    checkpoint_file = f"{output_file}.checkpoint"
    
    if os.path.exists(checkpoint_file) and start_from == 0:
        try:
            with open(checkpoint_file, 'r') as f:
                start_from = int(f.read().strip())
                print(f"[*] 从上次中断点继续处理: 第 {start_from} 笔")
        except Exception as e:
            print(f"[!] 读取断点文件时发生错误: {e}")
            start_from = 0
    
    try:
        # 使用pandas读取CSV文件
        df = pd.read_csv(csv_file, encoding='utf-8')
        print(f"[*] CSV 欄位名稱: {list(df.columns)}")
        print(f"[*] 读取到 {len(df)} 筆資料")
    except Exception as e:
        print(f"[!] 读取 CSV 文件時发生错误: {e}")
        return
    
    # 确保'm3u8'列存在
    if 'm3u8' not in df.columns:
        df['m3u8'] = ""
    
    # 如果输出文件已存在，尝试从中加载已处理的数据
    if os.path.exists(output_file) and start_from == 0:
        try:
            output_df = pd.read_csv(output_file, encoding='utf-8')
            # 将已处理的m3u8数据合并到当前DataFrame
            for i, row in output_df.iterrows():
                if pd.notna(row.get('m3u8')) and row.get('m3u8'):
                    # 找到对应的行
                    matching_rows = df[df['url'] == row['url']]
                    if not matching_rows.empty:
                        idx = matching_rows.index[0]
                        df.at[idx, 'm3u8'] = row['m3u8']
                        print(f"[*] 从输出文件加载已处理数据: {row['url']} -> {row['m3u8']}")
        except Exception as e:
            print(f"[!] 加载输出文件数据时发生错误: {e}")
    
    tasks = []
    for i, row in df.iloc[start_from:].iterrows():
        if pd.isna(row.get('url')):
            print(f"[!] 第 {i+1} 筆資料缺少 URL，跳過")
            continue
        
        # 如果已经有m3u8数据，跳过
        if not pd.isna(row.get('m3u8')) and row.get('m3u8') != "":
            print(f"[*] 第 {i+1} 筆資料已有 m3u8 数据，跳过")
            continue
        
        url = str(row['url']).strip()
        file_name = row.get(df.columns[0], f"項目 {i+1}")
        
        tasks.append((i, url, file_name, row))
    
    if not tasks:
        print("[*] 沒有需要處理的任務或全部已完成")
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
        # 保存最终结果
        df.to_csv(output_file, index=False, encoding='utf-8')
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
            future_to_task = {
                executor.submit(process_url, url, file_name, i, len(df)): (i, row)
                for i, url, file_name, row in current_batch
            }
            
            for future in concurrent.futures.as_completed(future_to_task):
                i, row = future_to_task[future]
                
                retry_count = 0
                result = None
                while retry_count < max_retries:
                    try:
                        result = future.result()
                        break
                    except Exception as e:
                        retry_count += 1
                        print(f"[!] 任務 {i+1} 執行失敗 (嘗試 {retry_count}/{max_retries}): {e}")
                        if retry_count < max_retries:
                            print(f"[*] 準備重試...")
                            time.sleep(2)
                        else:
                            print(f"[!] 達到最大重試次數，跳過")
                            result = ""
                
                # 更新DataFrame中的m3u8值
                df.at[i, 'm3u8'] = result
                processed_count += 1
                
                with open(checkpoint_file, 'w') as f:
                    f.write(str(i + 1))
                
                try:
                    # 每完成一个任务就保存CSV
                    df.to_csv(output_file, index=False, encoding='utf-8')
                    print(f"[*] 已处理 {processed_count}/{len(tasks)} 筆資料，已將結果儲存至 {output_file}")
                except Exception as e:
                    print(f"[!] 儲存 CSV 檔案時發生錯誤: {e}")
                
        batch_progress = (batch_end / len(tasks)) * 100
        print(f"[*] 已完成 {batch_end}/{len(tasks)} 筆任務 ({batch_progress:.1f}%)")
        print(f"[*] 休息 2 秒后继续下一批...")
        time.sleep(2)
    
    try:
        # 最终保存结果
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"[*] 全部處理完成，最終結果已儲存至 {output_file}")
        
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
    except Exception as e:
        print(f"[!] 最終儲存 CSV 檔案時發生錯誤: {e}")
    
    print(f"[*] 處理完成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='批量獲取 m3u8 連結')
    parser.add_argument('--csv', type=str, default="consensus_test.csv", help='CSV 文件路徑')
    parser.add_argument('--workers', type=int, default=2, help='並行處理的線程數')
    parser.add_argument('--save', type=int, default=5, help='每處理多少條數據保存一次')
    parser.add_argument('--start', type=int, default=0, help='從第幾條數據開始處理')
    parser.add_argument('--retries', type=int, default=3, help='重試次數')
    parser.add_argument('--output', type=str, default="task_m3u8.csv", help='输出CSV文件名')
    args = parser.parse_args()
    
    process_csv(args.csv, args.workers, args.save, args.start, args.retries, args.output)