import os
import subprocess
import sys
import time
import threading

def log_stream(proc, name):
    for line in iter(proc.stdout.readline, ''):
        if line:
            print(f"[{name}] {line.strip()}")
    proc.stdout.close()

def run():
    print("=" * 80)
    print("                 STARTING FINANCIAL MIRROR APPLICATION")
    print("=" * 80)
    
    # 1. Start backend FastAPI server
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
    
    # Resolve the python executable in venv (located in root workspace)
    root_dir = os.path.abspath(os.path.dirname(__file__))
    venv_python = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        # Try relative to backend just in case
        venv_python = os.path.join(backend_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        # Fallback to system python
        venv_python = sys.executable

    print(f"[+] Starting FastAPI Backend using: {venv_python}")
    backend_proc = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # 2. Start frontend Next.js dev server
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend"))
    print("[+] Starting Next.js Frontend using: npm run dev")
    
    # Use shell=True for windows npm command resolution
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=True
    )
    
    # Threading for real-time console log streaming
    t1 = threading.Thread(target=log_stream, args=(backend_proc, "BACKEND"), daemon=True)
    t2 = threading.Thread(target=log_stream, args=(frontend_proc, "FRONTEND"), daemon=True)
    t1.start()
    t2.start()

    print("\n[v] Financial Mirror is running!")
    print("    - Backend API:        http://localhost:8000")
    print("    - Frontend Dashboard: http://localhost:3000")
    print("    - Press Ctrl+C to stop both servers.\n")
    
    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print(f"[!] Backend process exited with code {backend_proc.poll()}.")
                break
            if frontend_proc.poll() is not None:
                print(f"[!] Frontend process exited with code {frontend_proc.poll()}.")
                break
    except KeyboardInterrupt:
        print("\n[+] Stopping servers...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        try:
            frontend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            frontend_proc.kill()
        print("[v] All servers stopped cleanly.")

if __name__ == "__main__":
    run()
