from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
import os
import time
import datetime
import concurrent.futures
import resource
import gc
import shutil
import tempfile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def increase_file_limit():
    """Attempts to increase system file descriptor limit"""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        print(f"[*] 當前系統文件描述符限制: 軟限制={soft}, 硬限制={hard}")
        
        if soft < hard:
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
            new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            print(f"[*] 已增加文件描述符限制: 新軟限制={new_soft}, 新硬限制={new_hard}")
    except Exception as e:
        print(f"[!] 增加文件描述符限制失败: {e}")

def create_seleniumwire_dirs():
    """Create necessary directories for Selenium Wire to store its data"""
    try:
        cache_dirs = [
            # 移除 macOS 特定路径
            os.path.join('/tmp', '.seleniumwire'),  # Ubuntu 常用临时目录
            os.path.join(tempfile.gettempdir(), '.seleniumwire'),  # 系统临时目录
            os.path.join(os.path.expanduser('~'), '.seleniumwire')  # 用户主目录
        ]
        
        for cache_dir in cache_dirs:
            if not os.path.exists(cache_dir):
                try:
                    print(f"[*] 創建 Selenium Wire 目錄: {cache_dir}")
                    os.makedirs(cache_dir, exist_ok=True)
                    os.chmod(cache_dir, 0o755)
                except Exception as e:
                    print(f"[!] 無法創建目錄 {cache_dir}: {e}")
    except Exception as e:
        print(f"[!] 創建 Selenium Wire 目錄時發生錯誤: {e}")

def clear_seleniumwire_cache():
    """Cleans Selenium Wire cache files and ensures directories exist"""
    try:
        cache_dirs = [
            # 移除 macOS 特定路径
            os.path.join('/tmp', '.seleniumwire'),  # Ubuntu 常用临时目录
            os.path.join(tempfile.gettempdir(), '.seleniumwire'),  # 系统临时目录
            os.path.join(os.path.expanduser('~'), '.seleniumwire')  # 用户主目录
        ]
        
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                print(f"[*] 正在清理 Selenium Wire 緩存: {cache_dir}")
                try:
                    shutil.rmtree(cache_dir)
                except Exception as e:
                    print(f"[!] 無法刪除目錄 {cache_dir}: {e}")
                    for root, dirs, files in os.walk(cache_dir):
                        for file in files:
                            try:
                                os.remove(os.path.join(root, file))
                            except:
                                pass
            
            try:
                print(f"[*] 重新創建 Selenium Wire 目錄: {cache_dir}")
                os.makedirs(cache_dir, exist_ok=True)
                os.chmod(cache_dir, 0o755)
            except Exception as e:
                print(f"[!] 無法創建目錄 {cache_dir}: {e}")
                
    except Exception as e:
        print(f"[!] 清理緩存時發生錯誤: {e}")

def get_m3u8_url(session_url):
    """Extracts the m3u8 URL from the given session URL"""
    start_time = time.time()
    print(f"[*] 開始時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    increase_file_limit()
    create_seleniumwire_dirs()
    clear_seleniumwire_cache()
    
    custom_storage_path = os.path.join(tempfile.gettempdir(), 'seleniumwire_custom_storage')
    os.makedirs(custom_storage_path, exist_ok=True)
    os.chmod(custom_storage_path, 0o755)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    
    seleniumwire_options = {
        'disable_encoding': True,
        'verify_ssl': False,
        'suppress_connection_errors': True,
        'connection_timeout': 10,
        'connection_keep_alive': False,
        'max_threads': 4,
        'pool_connections': 10,
        'pool_maxsize': 10,
        'request_storage_base_dir': custom_storage_path
    }
    
    driver = None
    try:
        driver = webdriver.Chrome(
            options=chrome_options,
            seleniumwire_options=seleniumwire_options
        )
        driver.set_page_load_timeout(20)
        
        driver.scopes = [
            '.*\.m3u8.*',
            '.*\/manifest.*',
            '.*jwplayer.*',
            '.*media.*'
        ]
        
        print("[*] 正在載入網頁...")
        driver.get(session_url)

        try:
            video_wait = WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.TAG_NAME, "video")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".jwplayer")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".vjs-tech"))
                )
            )
            print("[*] 偵測到影片元素")
            
            time.sleep(2)
        except Exception as e:
            print(f"[!] 等待影片載入時發生錯誤: {e}")
            print("[*] 繼續檢查網絡請求...")
            time.sleep(2)

        m3u8_url = None
        m3u8_candidates = []
        print("[*] 搜尋m3u8連結...")
        
        if len(driver.requests) > 100:
            print(f"[*] 請求數量過多({len(driver.requests)}個)，只分析最近的100個請求")
            requests_to_analyze = driver.requests[-100:]
        else:
            requests_to_analyze = driver.requests
            
        def analyze_url(request):
            results = []
            if not request.response:
                return results
                
            if ".m3u8" in request.url:
                results.append(request.url)
                
            if "jwplayer" in request.url and "ping.gif" in request.url and "mu=" in request.url:
                try:
                    from urllib.parse import urlparse, parse_qs
                    parsed_url = urlparse(request.url)
                    query_params = parse_qs(parsed_url.query)
                    
                    if 'mu' in query_params:
                        embedded_m3u8 = query_params['mu'][0]
                        results.append(embedded_m3u8)
                        print(f"[*] 從JWPlayer參數中提取到m3u8: {embedded_m3u8}")
                except Exception as e:
                    print(f"[!] 從URL參數提取m3u8失敗: {e}")
            
            return results
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            request_results = list(executor.map(analyze_url, requests_to_analyze))
            
        for result in request_results:
            m3u8_candidates.extend(result)
        
        gc.collect()
        
        if m3u8_candidates:
            print(f"[*] 找到 {len(m3u8_candidates)} 個可能的m3u8連結")
            
            for url in m3u8_candidates:
                if "cdn.jwplayer.com/manifests" in url:
                    m3u8_url = url
                    print(f"[*] 選擇JWPlayer主要清單: {url}")
                    break
                elif "/media/" in url or "/manifest" in url or "/master" in url:
                    m3u8_url = url
                    print(f"[*] 選擇含有media/manifest/master的URL: {url}")
                    break
            
            if not m3u8_url:
                for url in m3u8_candidates:
                    if "ping" not in url.lower() and "analytics" not in url.lower() and "track" not in url.lower():
                        m3u8_url = url
                        print(f"[*] 選擇非跟踪用的m3u8: {url}")
                        break
            
            if not m3u8_url and m3u8_candidates:
                m3u8_url = m3u8_candidates[0]
                print(f"[*] 使用第一個找到的m3u8: {m3u8_url}")
        
        if not m3u8_url:
            print("[*] 嘗試從JS獲取m3u8...")
            try:
                video_sources = driver.execute_script("""
                    var sources = [];
                    var videos = document.getElementsByTagName('video');
                    for(var i=0; i<videos.length; i++) {
                        if(videos[i].src && videos[i].src.includes('.m3u8')) {
                            sources.push(videos[i].src);
                        }
                    }
                    if(window.jwplayer) {
                        var players = jwplayer();
                        if(players) {
                            var config = players.getConfig();
                            if(config && config.sources) {
                                for(var i=0; i<config.sources.length; i++) {
                                    if(config.sources[i].file && config.sources[i].file.includes('.m3u8')) {
                                        sources.push(config.sources[i].file);
                                    }
                                }
                            }
                        }
                    }
                    return sources;
                """)
                
                if video_sources and len(video_sources) > 0:
                    m3u8_url = video_sources[0]
                    print(f"[*] 從JS提取到m3u8: {m3u8_url}")
            except Exception as e:
                print(f"[!] JS提取m3u8失敗: {e}")
        
        return m3u8_url
    
    except Exception as e:
        print(f"[!] 獲取m3u8時發生錯誤: {e}")
        return None
    
    finally:
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"[*] 結束時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[*] 總耗時: {elapsed_time:.2f} 秒")
        
        if driver:
            try:
                del driver.requests
                driver.quit()
            except Exception as e:
                print(f"[!] 關閉 driver 時發生錯誤: {e}")
        
        gc.collect()
        clear_seleniumwire_cache()

def download_with_ffmpeg(m3u8_url, output_filename):
    """Downloads the media using ffmpeg"""
    if not m3u8_url:
        print("[!] 沒有找到 m3u8 真實連結，無法下載")
        return

    start_time = time.time()
    print(f"[*] 開始下載時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    cmd = f'ffmpeg -y -http_persistent false -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 ' \
          f'-i "{m3u8_url}" -vn -acodec libmp3lame -ab 128k -threads 4 -buffer_size 8192k "{output_filename}"'
    print(f"[*] 執行命令：{cmd}")
    os.system(cmd)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[*] 下載結束時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] 下載總耗時: {elapsed_time:.2f} 秒")

if __name__ == "__main__":
    total_start_time = time.time()
    print(f"[*] 程序開始時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    session_url = "https://consensus-hongkong2025.coindesk.com/agenda/event/-global-regulation-panel-35"
    output_filename = f"consensus_audio_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    
    m3u8_url = get_m3u8_url(session_url)
    if m3u8_url:
        print(f"[*] 找到 m3u8 真實網址：{m3u8_url}")
    else:
        print("[!] 無法找到 m3u8 連結，請確認影片已載入。")
    
    total_end_time = time.time()
    total_elapsed_time = total_end_time - total_start_time
    print(f"[*] 程序結束時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] 程序總耗時: {total_elapsed_time:.2f} 秒")
