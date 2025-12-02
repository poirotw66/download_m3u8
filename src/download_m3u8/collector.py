from __future__ import annotations

import concurrent.futures
import datetime
import gc
import os
import shutil
import tempfile
import time
from typing import Iterable, List, Optional

import resource
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CACHE_DIRS: List[str] = [
    os.path.join("/tmp", ".seleniumwire"),
    os.path.join(tempfile.gettempdir(), ".seleniumwire"),
    os.path.join(os.path.expanduser("~"), ".seleniumwire"),
]


def increase_file_limit() -> None:
    """Attempt to raise the soft file descriptor limit to the hard limit."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        print(f"[*] 當前系統文件描述符限制: 軟限制={soft}, 硬限制={hard}")
        if soft < hard:
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
            new_soft, new_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            print(f"[*] 已增加文件描述符限制: 新軟限制={new_soft}, 新硬限制={new_hard}")
    except Exception as exc:
        print(f"[!] 增加文件描述符限制失敗: {exc}")


def _create_seleniumwire_dirs() -> None:
    for cache_dir in CACHE_DIRS:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            os.chmod(cache_dir, 0o755)
        except Exception as exc:
            print(f"[!] 無法創建目錄 {cache_dir}: {exc}")


def clear_seleniumwire_cache() -> None:
    """Remove Selenium Wire cache directories to avoid stale files."""
    for cache_dir in CACHE_DIRS:
        if os.path.exists(cache_dir):
            print(f"[*] 正在清理 Selenium Wire 緩存: {cache_dir}")
            try:
                shutil.rmtree(cache_dir)
            except Exception as exc:
                print(f"[!] 無法刪除目錄 {cache_dir}: {exc}")
                for root, _dirs, files in os.walk(cache_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except OSError:
                            pass
        try:
            os.makedirs(cache_dir, exist_ok=True)
            os.chmod(cache_dir, 0o755)
            print(f"[*] 重新創建 Selenium Wire 目錄: {cache_dir}")
        except Exception as exc:
            print(f"[!] 無法創建目錄 {cache_dir}: {exc}")


def _build_chrome_options(headless: bool) -> Options:
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    return chrome_options


def _analyze_url_request(request) -> List[str]:
    """Extract candidate m3u8 urls from a seleniumwire request."""
    candidates: List[str] = []
    if not getattr(request, "response", None):
        return candidates

    if ".m3u8" in request.url:
        candidates.append(request.url)

    if "jwplayer" in request.url and "ping.gif" in request.url and "mu=" in request.url:
        try:
            from urllib.parse import parse_qs, urlparse

            parsed_url = urlparse(request.url)
            query_params = parse_qs(parsed_url.query)
            if "mu" in query_params:
                embedded = query_params["mu"][0]
                candidates.append(embedded)
                print(f"[*] 從JWPlayer參數提取到m3u8: {embedded}")
        except Exception as exc:
            print(f"[!] 從URL參數提取m3u8失敗: {exc}")

    return candidates


def get_m3u8_url(
    session_url: str,
    *,
    headless: bool = True,
    wait_timeout: int = 10,
    max_requests_to_scan: int = 100,
) -> Optional[str]:
    """
    Extract the first plausible m3u8 URL from a conference session page.

    Parameters
    ----------
    session_url:
        Session page URL containing the embedded player.
    headless:
        Whether to run Chrome in headless mode.
    wait_timeout:
        Seconds to wait for player elements to appear.
    max_requests_to_scan:
        Maximum seleniumwire requests to inspect for performance reasons.
    """

    start_time = time.time()
    print(f"[*] 開始時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    increase_file_limit()
    _create_seleniumwire_dirs()
    clear_seleniumwire_cache()

    custom_storage_path = os.path.join(tempfile.gettempdir(), "seleniumwire_custom_storage")
    os.makedirs(custom_storage_path, exist_ok=True)
    os.chmod(custom_storage_path, 0o755)

    seleniumwire_options = {
        "disable_encoding": True,
        "verify_ssl": False,
        "suppress_connection_errors": True,
        "connection_timeout": 10,
        "connection_keep_alive": False,
        "max_threads": 4,
        "pool_connections": 10,
        "pool_maxsize": 10,
        "request_storage_base_dir": custom_storage_path,
    }

    driver = None
    m3u8_url: Optional[str] = None

    try:
        driver = webdriver.Chrome(options=_build_chrome_options(headless), seleniumwire_options=seleniumwire_options)
        driver.set_page_load_timeout(20)
        driver.scopes = [r".*\.m3u8.*", r".*/manifest.*", r".*jwplayer.*", r".*media.*"]

        print("[*] 正在載入網頁...")
        driver.get(session_url)

        try:
            WebDriverWait(driver, wait_timeout).until(
                EC.any_of(
                    EC.presence_of_element_located((By.TAG_NAME, "video")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".jwplayer")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".vjs-tech")),
                )
            )
            print("[*] 偵測到影片元素")
            time.sleep(2)
        except Exception as exc:
            print(f"[!] 等待影片載入時發生錯誤: {exc}")
            print("[*] 繼續檢查網絡請求...")
            time.sleep(2)

        print("[*] 搜尋m3u8連結...")
        requests_to_analyze = (
            driver.requests[-max_requests_to_scan:]
            if len(driver.requests) > max_requests_to_scan
            else driver.requests
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            candidate_batches = executor.map(_analyze_url_request, requests_to_analyze)

        m3u8_candidates = [candidate for batch in candidate_batches for candidate in batch]
        gc.collect()

        if m3u8_candidates:
            print(f"[*] 找到 {len(m3u8_candidates)} 個可能的m3u8連結")
            m3u8_url = _prioritize_candidates(m3u8_candidates)

        if not m3u8_url:
            print("[*] 嘗試從JS獲取m3u8...")
            try:
                video_sources = driver.execute_script(
                    """
                    const sources = [];
                    const videos = document.getElementsByTagName('video');
                    for (let i = 0; i < videos.length; i += 1) {
                        if (videos[i].src && videos[i].src.includes('.m3u8')) {
                            sources.push(videos[i].src);
                        }
                    }
                    if (window.jwplayer) {
                        const instance = jwplayer();
                        if (instance) {
                            const config = instance.getConfig();
                            if (config && config.sources) {
                                for (let i = 0; i < config.sources.length; i += 1) {
                                    const source = config.sources[i];
                                    if (source.file && source.file.includes('.m3u8')) {
                                        sources.push(source.file);
                                    }
                                }
                            }
                        }
                    }
                    return sources;
                    """
                )
                if video_sources:
                    m3u8_url = video_sources[0]
                    print(f"[*] 從JS提取到m3u8: {m3u8_url}")
            except Exception as exc:
                print(f"[!] JS提取m3u8失敗: {exc}")

        return m3u8_url
    except Exception as exc:
        print(f"[!] 獲取m3u8時發生錯誤: {exc}")
        return None
    finally:
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"[*] 結束時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[*] 總耗時: {elapsed:.2f} 秒")

        if driver:
            try:
                del driver.requests
                driver.quit()
            except Exception as exc:  # pragma: no cover - best effort cleanup
                print(f"[!] 關閉 driver 時發生錯誤: {exc}")

        gc.collect()
        clear_seleniumwire_cache()


def _prioritize_candidates(candidates: Iterable[str]) -> Optional[str]:
    prioritized_keywords = [
        "cdn.jwplayer.com/manifests",
        "/media/",
        "/manifest",
        "/master",
    ]
    for keyword in prioritized_keywords:
        for candidate in candidates:
            if keyword in candidate:
                print(f"[*] 選擇匹配 {keyword} 的m3u8: {candidate}")
                return candidate

    for candidate in candidates:
        lowered = candidate.lower()
        if "ping" not in lowered and "analytics" not in lowered and "track" not in lowered:
            print(f"[*] 選擇非追蹤m3u8: {candidate}")
            return candidate

    fallback = next(iter(candidates), None)
    if fallback:
        print(f"[*] 使用第一個找到的m3u8: {fallback}")
    return fallback

