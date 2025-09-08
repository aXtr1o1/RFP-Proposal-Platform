import time, os
import requests

def poll_vision_result(operation_location: str, timeout=120):
    vision_key = os.getenv("AZURE_VISION_KEY")
    headers = {"Ocp-Apim-Subscription-Key": vision_key}
    
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(operation_location, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status")
            if status == "succeeded":
                print(f"OCR completed successfully")
                return result
            elif status == "failed":
                print(f"OCR failed: {result}")
                return None
            else:
                print(f"OCR status: {status}, waiting...")
                time.sleep(2)
        except Exception as e:
            print(f"Error polling OCR result: {e}")
            time.sleep(2)
    
    print("OCR polling timeout")
    return None

def run():
    print("[worker] OCR worker started (stub).")
    while True:
        # TODO: poll API/queue for OCR tasks, call Azure Vision (primary) or pytesseract
        # For now, just keep the worker alive
        time.sleep(5)

if __name__ == "__main__":
    run()
