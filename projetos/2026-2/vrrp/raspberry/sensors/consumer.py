import fcntl
import json
import os
import time
import requests

API_URL = "http://192.168.15.7:4000/api/sensors"
STORAGE_FILE = os.path.expanduser("~/sensors/storage.jsonl")
TMP_FILE = os.path.expanduser("~/sensors/tmp.jsonl")
THIRTY_SECONDS = 30
ONE_MINUTE_IN_SEC = 60

def send_to_server(data):
    try:
        response = requests.post(API_URL, json=data, timeout=60)
        return 201 <= response.status_code == 201
    except Exception as e:
        print(f"[WORKER] Failed to send record (HTTP {response.status_code}). Retrying...")
        return False

def read_first_line():
    if not os.path.exists(STORAGE_FILE) or os.path.getsize(STORAGE_FILE) == 0:
        return None

    with open(STORAGE_FILE, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            line = f.readline()
            return line.strip() if line else None
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

def delete_first_line():
    if not os.path.exists(STORAGE_FILE) or os.path.getsize(STORAGE_FILE) == 0:
        return

    with open(STORAGE_FILE, "r") as src:
        fcntl.flock(src, fcntl.LOCK_EX)
        try:
            with open(TMP_FILE, "w") as dst:
                for i, line in enumerate(src):
                    if i == 0:
                        continue
                    dst.write(line)

            os.replace(TMP_FILE, STORAGE_FILE)

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error deleting first line: {e}")
            if os.path.exists(TMP_FILE):
                os.remove(TMP_FILE)
        finally: 
            fcntl.flock(src, fcntl.LOCK_UN)

def main():
    print("CONSUMER STARTED...")
    while True:
        try:
            line = read_first_line()

            try:
                data = json.loads(line)            
            except json.JSONDecodeError:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Corrupted JSON line found, removing it.")
                delete_first_line()
                continue

            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sending data to server...")
            result = send_to_server(data)

            if result:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Successfully sent! Remove line from storage...")
                delete_first_line() 
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Server request failed. Retrying in {ONE_MINUTE_IN_SEC}s...")
                time.sleep(ONE_MINUTE_IN_SEC)

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error in consumer: {e}")

        time.sleep(THIRTY_SECONDS)

if __name__ == "__main__":
    main()       
