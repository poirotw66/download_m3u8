import csv
import os
import subprocess
import time
import datetime
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create a lock for thread-safe printing
print_lock = threading.Lock()

def safe_print(message):
    """Thread-safe print function"""
    with print_lock:
        print(message)

def download_aac_from_m3u8(m3u8_url, output_filename):
    """Downloads AAC audio from m3u8 URL using ffmpeg with optimized parameters"""
    safe_print(f"[*] Downloading: {output_filename}")
    start_time = time.time()
    
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    
    # Sanitize filename by replacing invalid characters
    safe_filename = output_filename.replace('/', '_').replace('\\', '_').replace(':', '_')
    output_path = os.path.join("output", f"{safe_filename}.aac")
    
    # Construct ffmpeg command with optimized parameters
    # -threads auto: Use all available CPU cores
    # -c copy: Copy without re-encoding
    # -bsf:a aac_adtstoasc: Fix AAC stream format
    # -protocol_whitelist: Allow various protocols needed for m3u8
    cmd = (
        f'ffmpeg -y -threads auto -protocol_whitelist file,http,https,tcp,tls,crypto '
        f'-i "{m3u8_url}" -vn -c:a copy -bsf:a aac_adtstoasc -progress pipe:1 "{output_path}"'
    )
    
    # Execute the command
    safe_print(f"[*] Running command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    # Check if the command was successful
    if result.returncode == 0:
        end_time = time.time()
        elapsed_time = end_time - start_time
        safe_print(f"[*] Download completed: {output_path}")
        safe_print(f"[*] Time taken: {elapsed_time:.2f} seconds")
        return True, output_filename
    else:
        safe_print(f"[!] Error downloading {output_filename}:")
        safe_print(f"[!] {result.stderr}")
        # Log error to file
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"Error downloading {output_filename} at {datetime.datetime.now()}:\n")
            error_file.write(f"{result.stderr}\n\n")
        return False, output_filename

def worker(task_queue, results):
    """Worker function for thread pool"""
    while True:
        try:
            # Get a task from the queue
            task = task_queue.get(block=False)
            if task is None:
                break
                
            file_name, m3u8_url = task
            success, filename = download_aac_from_m3u8(m3u8_url, file_name)
            results.append((success, filename))
            
        except queue.Empty:
            break
        except Exception as e:
            safe_print(f"[!] Worker error: {str(e)}")
            results.append((False, str(e)))
        finally:
            # Mark task as done
            task_queue.task_done()

def main():
    csv_file = "consensus_test.csv"
    max_threads = min(os.cpu_count(), 8)  # Use at most 8 threads or number of CPU cores
    safe_print(f"[*] Reading CSV file: {csv_file}")
    safe_print(f"[*] Using {max_threads} parallel download threads")
    
    # Track overall statistics
    total_start_time = time.time()
    successful_downloads = 0
    failed_downloads = 0
    tasks = queue.Queue()
    results = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as file:
            # Skip any lines that start with //
            lines = [line for line in file if not line.strip().startswith('//')]
            
            # Create a new csv reader from the filtered lines
            csv_reader = csv.DictReader(lines)
            
            # Print the field names to diagnose issues
            safe_print(f"[*] CSV columns found: {csv_reader.fieldnames}")
            
            # Validate that the CSV has the required columns
            if not all(field in csv_reader.fieldnames for field in ["\ufefffile", "m3u8"]):
                safe_print("[!] The CSV file is missing required columns. It should have 'file' and 'm3u8' columns.")
                return
            
            # Queue all download tasks
            for row in csv_reader:
                file_name = row["\ufefffile"]
                m3u8_url = row["m3u8"]
                
                if not m3u8_url:
                    safe_print(f"[!] No m3u8 URL provided for {file_name}, skipping.")
                    failed_downloads += 1
                    continue
                
                # Add task to queue
                tasks.put((file_name, m3u8_url))
                
            # Create and start worker threads
            threads = []
            for _ in range(max_threads):
                thread = threading.Thread(target=worker, args=(tasks, results))
                thread.start()
                threads.append(thread)
                
            # Wait for all tasks to complete
            tasks.join()
            
            # Stop all threads
            for _ in range(max_threads):
                tasks.put(None)
                
            # Wait for all threads to finish
            for thread in threads:
                thread.join()
            
            # Process results
            for success, filename in results:
                if success:
                    successful_downloads += 1
                else:
                    failed_downloads += 1
    
    except FileNotFoundError:
        safe_print(f"[!] CSV file not found: {csv_file}")
        return
    except Exception as e:
        safe_print(f"[!] An error occurred: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Print summary
    total_end_time = time.time()
    total_elapsed_time = total_end_time - total_start_time
    safe_print("\n" + "=" * 50)
    safe_print("[*] Download Summary:")
    safe_print(f"[*] Total files processed: {successful_downloads + failed_downloads}")
    safe_print(f"[*] Successfully downloaded: {successful_downloads}")
    safe_print(f"[*] Failed downloads: {failed_downloads}")
    safe_print(f"[*] Total time taken: {total_elapsed_time:.2f} seconds")
    safe_print("=" * 50)

if __name__ == "__main__":
    safe_print(f"[*] Starting batch download at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    main()
    safe_print(f"[*] Batch download completed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
