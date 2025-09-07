# minimal stub worker
import time, os

def run():
    print("[worker] OCR worker started (stub).")
    while True:
        # TODO: poll API/queue for OCR tasks, call Azure Vision (primary) or pytesseract
        time.sleep(5)

if __name__ == "__main__":
    run()
