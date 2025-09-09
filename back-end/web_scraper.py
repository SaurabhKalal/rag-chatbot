import os
import subprocess
import time

# Absolute path to Scrapy project root
SCRAPY_PROJECT_DIR = os.path.abspath("scrapy_web_scraper")
OUTPUT_PATH = os.path.join(SCRAPY_PROJECT_DIR, "output.json")

def run_scrapy_spider(start_url: str, output_path: str = OUTPUT_PATH, timeout: int = 120):
    command = f'scrapy crawl universal_spider -a start_url="{start_url}" -o "{output_path}"'

    process = subprocess.Popen(
        command,
        shell=True,
        cwd=SCRAPY_PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError(f"Scrapy spider timed out after {timeout} seconds")

    print("Scrapy stdout:", stdout.decode())
    print("Scrapy stderr:", stderr.decode())

    if process.returncode != 0:
        raise RuntimeError(f"Scrapy spider failed:\n{stderr.decode()}")

    # Wait for output.json to appear with content
    start_time = time.time()
    while not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Timed out waiting for output.json at {output_path}")
        time.sleep(1)
