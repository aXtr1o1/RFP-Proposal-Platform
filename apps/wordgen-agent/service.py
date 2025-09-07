# Windows Word COM agent (run on Windows with Office installed)
import time, os, requests
try:
    import win32com.client as win32
except Exception as e:
    win32 = None

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
TEMPLATE = os.getenv("DOC_TEMPLATE_PATH", r"C:\agent\Templates\Proposal.dotx")
OUT_DIR = os.getenv("ONEDRIVE_SYNC_DIR", r"C:\Users\Public\Documents")

def build_doc(job):
    word = win32.gencache.EnsureDispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Add(TEMPLATE)
    # TODO: fill with job["sections"]
    out_path = os.path.join(OUT_DIR, f'{job["job_id"]}.docx')
    doc.SaveAs2(out_path)
    doc.Close(False)
    word.Quit()
    return out_path

def main():
    if win32 is None:
        print("win32 not available. Install pywin32 and run on Windows.")
        return
    while True:
        try:
            r = requests.get(f"{API_BASE}/jobs/wordgen/next", timeout=10)
            r.raise_for_status()
            job = r.json()
            if job and job.get("job_id"):
                path = build_doc(job)
                requests.post(f"{API_BASE}/jobs/{job['job_id']}/complete", json={"path": path}, timeout=10)
        except Exception as e:
            # TODO: better logging
            pass
        time.sleep(5)

if __name__ == "__main__":
    main()
