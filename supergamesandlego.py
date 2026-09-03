#!/usr/bin/env python3
"""
SUPERGAMESANDLEGO - Hardware Diagnostics & Stress Framework
Optimized for Linux & Windows (Intel i9 / AMD Ryzen / NVIDIA RTX / RAM / Drives).
Ensures STABLE 100% LOAD & 0% IDLE without Python Runtime/Semaphore Leaks.
"""

import os
import sys
import time
import tty
import termios
import subprocess
import multiprocessing
import threading
import signal
import json
from datetime import datetime

# ==============================================================================
# 0. AUTOMATED DEPENDENCY CHECKER
# ==============================================================================

class DependencyChecker:
    @staticmethod
    def check_and_prompt():
        missing = []
        try:
            import numpy
        except ImportError:
            missing.append("python3-numpy")

        glmark_installed = subprocess.run(["which", "glmark2"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        gpu_burn_installed = subprocess.run(["which", "gpu_burn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        sensors_installed = subprocess.run(["which", "sensors"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

        if not (glmark_installed or gpu_burn_installed):
            missing.append("glmark2")
        if not sensors_installed:
            missing.append("lm-sensors")

        if not missing:
            return

        print("================================================================================")
        print(" SUPERGAMESANDLEGO - DEPENDENCY CHECK")
        print("================================================================================")
        print(f" [!] Recommended packages missing: {', '.join(missing)}")
        
        try:
            choice = input(f"\n Install missing diagnostic tools via apt? [Y/n]: ").strip().lower()
        except KeyboardInterrupt:
            return

        if choice in ['', 'y', 'yes']:
            try:
                subprocess.run(["sudo", "apt", "update"])
                subprocess.run(["sudo", "apt", "install", "-y", "python3-numpy", "glmark2", "lm-sensors"])
            except Exception as e:
                print(f"[ERROR] Could not install dependencies: {e}")

# ==============================================================================
# 1. KEYBOARD INPUT CONTROLLER (RAW TERMINAL MODE)
# ==============================================================================

def get_key():
    """Reads a single keypress directly without requiring Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            if ch3 == 'A': return 'UP'
            if ch3 == 'B': return 'DOWN'
            if ch3 == 'Z': return 'SHIFT_TAB'
            return 'ESC'
        elif ch == '\t': return 'TAB'
        elif ch == ' ': return 'SPACE'
        elif ch in ['\r', '\n']: return 'ENTER'
        return ch.upper()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# ==============================================================================
# 2. HARDWARE VALIDATORS & ENHANCED SENSORS
# ==============================================================================

class HardwareValidator:
    @staticmethod
    def get_bios_and_microcode():
        info = {"bios_vendor": "N/A", "bios_version": "N/A", "bios_date": "N/A", "microcode": "N/A"}
        try:
            with open("/sys/class/dmi/id/bios_vendor", "r") as f: info["bios_vendor"] = f.read().strip()
            with open("/sys/class/dmi/id/bios_version", "r") as f: info["bios_version"] = f.read().strip()
            with open("/sys/class/dmi/id/bios_date", "r") as f: info["bios_date"] = f.read().strip()
        except Exception:
            pass

        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "microcode" in line:
                        info["microcode"] = line.split(":")[1].strip()
                        break
        except Exception:
            pass
        return info

class FanSensors:
    @staticmethod
    def get_fan_speeds():
        fans = {}
        hwmon_base = "/sys/class/hwmon"
        if os.path.exists(hwmon_base):
            for dir_name in os.listdir(hwmon_base):
                path = os.path.join(hwmon_base, dir_name)
                for file in os.listdir(path):
                    if file.startswith("fan") and file.endswith("_input"):
                        try:
                            with open(os.path.join(path, file), "r") as f:
                                rpm = int(f.read().strip())
                                fans[f"{dir_name}_{file.split('_')[0]}"] = rpm
                        except Exception:
                            pass
        return fans

class HardwareSensors:
    @staticmethod
    def get_system_resources():
        cores = multiprocessing.cpu_count()
        total_ram_gb = 0
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        kb = int(line.split()[1])
                        total_ram_gb = round(kb / (1024 * 1024), 1)
                        break
        except Exception:
            pass
        return cores, total_ram_gb

    @staticmethod
    def get_all_temperatures():
        metrics = {}

        hwmon_base = "/sys/class/hwmon"
        if os.path.exists(hwmon_base):
            for dir_name in os.listdir(hwmon_base):
                path = os.path.join(hwmon_base, dir_name)
                name_file = os.path.join(path, "name")
                sensor_name = "hwmon"
                
                if os.path.exists(name_file):
                    try:
                        with open(name_file, "r") as f:
                            sensor_name = f.read().strip()
                    except Exception:
                        pass

                for file in os.listdir(path):
                    if file.startswith("temp") and file.endswith("_input"):
                        try:
                            with open(os.path.join(path, file), "r") as f:
                                temp_raw = int(f.read().strip())
                                temp_c = temp_raw // 1000 if temp_raw > 1000 else temp_raw
                                
                                label_file = os.path.join(path, file.replace("_input", "_label"))
                                label_name = file.split('_')[0]
                                if os.path.exists(label_file):
                                    try:
                                        with open(label_file, "r") as lf:
                                            label_name = lf.read().strip()
                                    except Exception:
                                        pass

                                key = f"{sensor_name} ({label_name})"
                                metrics[key] = temp_c
                        except Exception:
                            pass

        try:
            res = subprocess.run(["sensors", "-j"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                for chip, sensors in data.items():
                    chip_name = chip.split("-")[0]
                    for sensor_key, values in sensors.items():
                        if isinstance(values, dict):
                            for key, val in values.items():
                                if key.endswith("_input") and isinstance(val, (int, float)):
                                    label = f"{chip_name} {sensor_key}"
                                    if label not in metrics:
                                        metrics[label] = int(val)
        except Exception:
            pass

        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
            if res.returncode == 0 and res.stdout.strip():
                gpu_temp = int(res.stdout.strip().split('\n')[0])
                metrics["NVIDIA GPU"] = gpu_temp
        except Exception:
            pass

        return metrics

# ==============================================================================
# 3. STORAGE DETECTOR WITH BUS/PORT DETAILS
# ==============================================================================

class StorageDetector:
    @staticmethod
    def get_physical_drives():
        drives = []
        block_base = "/sys/block"

        if os.path.exists(block_base):
            for dev in sorted(os.listdir(block_base)):
                if dev.startswith(("loop", "ram", "sr", "zram")):
                    continue

                device_path = os.path.join(block_base, dev)
                model_file = os.path.join(device_path, "device", "model")
                
                model_name = dev.upper()
                if os.path.exists(model_file):
                    try:
                        with open(model_file, "r") as f:
                            model_name = f.read().strip()
                    except Exception:
                        pass

                drives.append({
                    "id": f"DRIVE_{dev}",
                    "device": f"/dev/{dev}",
                    "name": f"{dev} ({model_name})"
                })

        return drives if drives else [{"id": "DRIVE_sda", "device": "/dev/sda", "name": "Primary Storage Drive"}]

    @staticmethod
    def get_physical_drives_extended():
        drives = []
        block_base = "/sys/block"

        if os.path.exists(block_base):
            for dev in sorted(os.listdir(block_base)):
                if dev.startswith(("loop", "ram", "sr", "zram")):
                    continue

                device_path = os.path.join(block_base, dev)
                model_file = os.path.join(device_path, "device", "model")
                
                model_name = "Generic Storage Device"
                if os.path.exists(model_file):
                    try:
                        with open(model_file, "r") as f:
                            model_name = f.read().strip()
                    except Exception:
                        pass

                port_info = "PCIe/SATA Port Unknown"
                try:
                    real_path = os.path.realpath(device_path)
                    if "nvme" in dev:
                        port_info = "NVMe PCIe Lane"
                    elif "ata" in real_path:
                        port_info = f"SATA Port {real_path.split('/')[-3]}"
                    elif "usb" in real_path:
                        port_info = "USB External Port"
                except Exception:
                    pass

                drives.append({
                    "device": f"/dev/{dev}",
                    "model": model_name,
                    "port": port_info
                })

        return drives

# ==============================================================================
# 4. NATIVE WORKERS (SUPPORTING PULSE / PAUSE MODE)
# ==============================================================================

def heavy_math_worker(stop_event, pause_event):
    """CPU Worker."""
    if os.name == 'posix':
        try:
            os.setsid()
        except Exception:
            pass
    x = 0.0001
    while not stop_event.is_set():
        if pause_event.is_set():
            time.sleep(0.05)
            continue
        x = (x + 1.000001) * 1.000001

def get_safe_ram_target():
    """Berekent 85% van het beschikbare fysieke geheugen."""
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemAvailable:' in line:
                    available_kb = int(line.split()[1])
                    available_mb = (available_kb / 1024) * 0.85
                    return int(available_mb)
    except Exception:
        pass
    return 2048

def heavy_ram_worker(size_mb, stop_event, pause_event):
    """RAM worker met directe fysieke geheugentoewijzing."""
    if os.name == 'posix':
        try:
            os.setsid()
        except Exception:
            pass
            
    bytes_count = int(size_mb * 1024 * 1024)
    allocated_data = None

    try:
        while not stop_event.is_set():
            if pause_event.is_set():
                if allocated_data is not None:
                    del allocated_data
                    allocated_data = None
                time.sleep(0.1)
                continue

            if allocated_data is None:
                try:
                    allocated_data = bytearray(b'\xFF' * bytes_count)
                except MemoryError:
                    time.sleep(0.5)
                    continue

            if not stop_event.is_set() and not pause_event.is_set():
                allocated_data[0::4096] = b'\xAA' * (len(allocated_data[0::4096]))
                time.sleep(0.01)

    except Exception:
        pass
    finally:
        if allocated_data is not None:
            del allocated_data

def heavy_drive_worker(target_device, stop_event, pause_event):
    if os.name == 'posix':
        try:
            os.setsid()
        except Exception:
            pass
    try:
        dev_name = target_device.replace("DRIVE_", "")
        temp_file = f"/tmp/sgal_drive_{dev_name}.tmp"
        with open(temp_file, "wb") as f:
            data = os.urandom(1024 * 1024 * 5)
            while not stop_event.is_set():
                if pause_event.is_set():
                    time.sleep(0.1)
                    continue
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
                f.seek(0)
    except Exception:
        pass

# ==============================================================================
# 5. STRESS ENGINE WITH AUTOMATIC PULSING SWITCH (HIGH / LOW)
# ==============================================================================

class StressEngine:
    def __init__(self, targets, pulsing=False, pulse_on_sec=8, pulse_off_sec=8):
        self.targets = targets
        self.active_processes = []
        self.mp_processes = []
        self.pulsing = pulsing
        self.pulse_on_sec = pulse_on_sec
        self.pulse_off_sec = pulse_off_sec
        self.pulse_thread = None
        self.is_running = False
        self.pulse_state = "100% HIGH LOAD" if not pulsing else "INIT PULSING"
        
        self.stop_event = multiprocessing.Event()
        self.pause_event = multiprocessing.Event()

    def _spawn_configured_workers(self):
        if "A" in self.targets:
            num_cores = multiprocessing.cpu_count()
            for _ in range(num_cores):
                p = multiprocessing.Process(target=heavy_math_worker, args=(self.stop_event, self.pause_event))
                p.daemon = True
                p.start()
                self.mp_processes.append(p)

        if "B" in self.targets:
            cores = multiprocessing.cpu_count()
            total_target_mb = get_safe_ram_target()
            mb_per_core = max(1, int(total_target_mb / cores))

            for _ in range(cores):
                p = multiprocessing.Process(target=heavy_ram_worker, args=(mb_per_core, self.stop_event, self.pause_event))
                p.daemon = True
                p.start()
                self.mp_processes.append(p)

        if "GPU" in self.targets:
            if subprocess.call(["which", "gpu_burn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                p = subprocess.Popen(
                    ["gpu_burn", "999999"], 
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if os.name == 'posix' else None
                )
                self.active_processes.append(p)
            elif subprocess.call(["which", "glmark2"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                p = subprocess.Popen(
                    ["glmark2", "--run-forever"], 
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if os.name == 'posix' else None
                )
                self.active_processes.append(p)

        for target in self.targets:
            if target.startswith("DRIVE_"):
                p = multiprocessing.Process(target=heavy_drive_worker, args=(target, self.stop_event, self.pause_event))
                p.daemon = True
                p.start()
                self.mp_processes.append(p)

    def _signal_external_binaries(self, sig):
        for p in self.active_processes:
            try:
                pgid = os.getpgid(p.pid)
                os.killpg(pgid, sig)
            except Exception:
                try:
                    os.kill(p.pid, sig)
                except Exception:
                    pass

    def start(self):
        self.is_running = True
        self.stop_event.clear()
        self.pause_event.clear()
        self._spawn_configured_workers()

        if self.pulsing:
            self.pulse_thread = threading.Thread(target=self._pulse_loop, daemon=True)
            self.pulse_thread.start()

    def _pulse_loop(self):
        while self.is_running:
            self.pulse_state = ">>> 100% HIGH LOAD <<<"
            self.pause_event.clear()
            self._signal_external_binaries(signal.SIGCONT)

            time.sleep(self.pulse_on_sec)

            if not self.is_running:
                break

            self.pulse_state = "<<< 0% LOW IDLE <<<"
            self.pause_event.set()
            self._signal_external_binaries(signal.SIGSTOP)

            time.sleep(self.pulse_off_sec)

    def stop_all(self):
        self.is_running = False
        self.stop_event.set()
        self.pause_event.clear()

        self._signal_external_binaries(signal.SIGCONT)

        for p in self.active_processes:
            try:
                p.terminate()
                p.wait(timeout=1)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self.active_processes.clear()

        for p in self.mp_processes:
            try:
                p.join(timeout=1)
                if p.is_alive():
                    p.terminate()
                if hasattr(p, 'close'):
                    p.close()
            except Exception:
                pass
        self.mp_processes.clear()

# ==============================================================================
# 6. DIAGNOSTIC LOGGER MODULE
# ==============================================================================

class DiagnosticLogger:
    def __init__(self):
        self.history = []
        self.start_time = time.time()
        self.stats = {}

    def log_snapshot(self, raw_data):
        elapsed = int(time.time() - self.start_time)
        m, s = divmod(elapsed, 60)
        time_str = f"{m}m {s}s" if m > 0 else f"{s}s"

        snapshot = {}
        for comp, cur_temp in raw_data.items():
            key = comp.lower().replace(" ", "").replace("_", "")

            if key not in self.stats:
                self.stats[key] = {
                    "cur": cur_temp,
                    "max": cur_temp,
                    "min": cur_temp,
                    "history": [cur_temp]
                }
            else:
                st = self.stats[key]
                st["cur"] = cur_temp
                st["max"] = max(st["max"], cur_temp)
                st["min"] = min(st["min"], cur_temp)
                st["history"].append(cur_temp)

            hist = self.stats[key]["history"]
            nominal = sum(hist) // len(hist)

            snapshot[key] = {
                "cur": cur_temp,
                "max": self.stats[key]["max"],
                "min": self.stats[key]["min"],
                "nom": nominal
            }

        self.history.append({'time': time_str, 'data': snapshot})

    def save_file(self):
        filename = f"sgal_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w') as f:
            f.write(f"SGAL DIAGNOSTICS REPORT - {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write("=" * 40 + "\n\n")

            bios_info = HardwareValidator.get_bios_and_microcode()
            f.write(f"BIOS Vendor: {bios_info['bios_vendor']}\n")
            f.write(f"BIOS Version: {bios_info['bios_version']} ({bios_info['bios_date']})\n")
            f.write(f"CPU Microcode: {bios_info['microcode']}\n")
            f.write("=" * 40 + "\n\n")

            for entry in self.history:
                f.write(f"timeintest {entry['time']}\n")
                for comp, stats in entry['data'].items():
                    f.write(f"{comp} {stats['cur']}°c\n")
                    f.write(f"{comp}max {stats['max']}°c\n")
                    f.write(f"{comp}min {stats['min']}°c\n")
                    f.write(f"{comp}nominal {stats['nom']}°c\n")
                f.write("\n")

        print(f"\n[SYSTEM] Diagnostic log report saved: {filename}")

# ==============================================================================
# 7. STANDALONE MENU: CLEANUP & DOWNLOAD (GRANULAR / ITEM-BY-ITEM)
# ==============================================================================

class CleanupDownloadMenu:
    def __init__(self):
        self.cursor = 0
        self.selected = set()
        self.deps = [
            ("python3-numpy", "Python3 NumPy Module"),
            ("glmark2", "GLMark2 OpenGL Benchmark"),
            ("lm-sensors", "LM-Sensors Hardware Thermal Monitor")
        ]
        self.refresh_items()

    def refresh_items(self):
        self.items = []
        
        for pkg, desc in self.deps:
            installed = subprocess.run(["dpkg", "-s", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            status = "INSTALLED" if installed else "MISSING"
            self.items.append({
                "id": f"INSTALL_{pkg}",
                "label": f"Install Dependency: {pkg:<15} [{status}] - {desc}",
                "action": "INSTALL",
                "pkg": pkg
            })

        for pkg, desc in self.deps:
            installed = subprocess.run(["dpkg", "-s", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            if installed:
                self.items.append({
                    "id": f"REMOVE_{pkg}",
                    "label": f"Delete Dependency:  {pkg:<15} - {desc}",
                    "action": "REMOVE",
                    "pkg": pkg
                })

        drives = StorageDetector.get_physical_drives_extended()
        for d in drives:
            self.items.append({
                "id": f"WIPE_{d['device']}",
                "label": f"Wipe Drive (Zero-Out): {d['device']} ({d['model']}) [{d['port']}]",
                "action": "WIPE",
                "device": d['device'],
                "model": d['model']
            })

        self.items.append({
            "id": "CLEAN_TMP",
            "label": "Clean Temp Files: Delete sgal_report_*.txt & /tmp temporary files",
            "action": "CLEAN_TMP"
        })

    def render(self):
        os.system('clear' if os.name == 'posix' else 'cls')
        print("================================================================================")
        print(" GRANULAR CLEANUP & DOWNLOAD MENU")
        print("================================================================================")
        print(" Navigation: [Tab / Arrow Keys] Move | [Spacebar] Select | [ENTER] Execute | [Q/ESC] Exit\n")

        current_action = None
        for idx, item in enumerate(self.items):
            if item["action"] != current_action:
                current_action = item["action"]
                if current_action == "INSTALL":
                    print("┌── [1] INSTALL DEPENDENCIES (SEPARATELY) ─────────────────────────────────────┐")
                elif current_action == "REMOVE":
                    print("└──────────────────────────────────────────────────────────────────────────────┘")
                    print("\n┌── [2] DELETE DEPENDENCIES (SEPARATELY) ──────────────────────────────────────┐")
                elif current_action == "WIPE":
                    print("└──────────────────────────────────────────────────────────────────────────────┘")
                    print("\n┌── [3] CLEAR & ZERO-OUT DRIVES (SEPARATELY) ─────────────────────────────────┐")
                elif current_action == "CLEAN_TMP":
                    print("└──────────────────────────────────────────────────────────────────────────────┘")
                    print("\n┌── [4] SYSTEM CLEANUP ────────────────────────────────────────────────────────┐")

            cur = ">" if idx == self.cursor else " "
            mark = "[*]" if item["id"] in self.selected else "[ ]"
            print(f"│ {cur} {mark} {item['label']:<70} │")

        print("└──────────────────────────────────────────────────────────────────────────────┘")
        print("\n Press [ENTER] to execute selected actions, or [Q] to return.")

    def run(self):
        while True:
            self.refresh_items()
            if self.cursor >= len(self.items):
                self.cursor = max(0, len(self.items) - 1)

            self.render()
            key = get_key()

            if key in ['DOWN', 'TAB']:
                self.cursor = (self.cursor + 1) % len(self.items)
            elif key in ['UP', 'SHIFT_TAB']:
                self.cursor = (self.cursor - 1) % len(self.items)
            elif key == 'SPACE':
                target_id = self.items[self.cursor]["id"]
                if target_id in self.selected:
                    self.selected.remove(target_id)
                else:
                    self.selected.add(target_id)
            elif key == 'ENTER':
                self._execute_actions()
                self.selected.clear()
                print("\nPress any key to continue...")
                get_key()
            elif key in ['ESC', 'Q']:
                break

    def _execute_actions(self):
        if not self.selected:
            print("\n[!] No items selected for execution.")
            return

        to_install, to_remove, to_wipe, clean_tmp = [], [], [], False

        for item in self.items:
            if item["id"] in self.selected:
                if item["action"] == "INSTALL":
                    to_install.append(item["pkg"])
                elif item["action"] == "REMOVE":
                    to_remove.append(item["pkg"])
                elif item["action"] == "WIPE":
                    to_wipe.append((item["device"], item["model"]))
                elif item["action"] == "CLEAN_TMP":
                    clean_tmp = True

        if to_install:
            print(f"\n[+] Installing selected dependencies: {', '.join(to_install)}")
            subprocess.run(["sudo", "apt", "update"])
            subprocess.run(["sudo", "apt", "install", "-y"] + to_install)

        if to_remove:
            print(f"\n[+] Removing selected dependencies: {', '.join(to_remove)}")
            subprocess.run(["sudo", "apt", "remove", "-y"] + to_remove)

        if to_wipe:
            print("\n================================================================================")
            print(" WARNING: DRIVE ZERO-OUT DATA DESTRUCTION")
            print("================================================================================")
            for dev, model in to_wipe:
                print(f" [!] Target Drive: {dev} ({model})")
            
            confirm = input("\nType 'DESTROY' in capital letters to confirm wiping ALL selected drives: ").strip()
            if confirm == "DESTROY":
                for dev, model in to_wipe:
                    print(f"\n[+] Overwriting {dev} with zeros via 'dd'...")
                    cmd = ["sudo", "dd", f"if=/dev/zero", f"of={dev}", "bs=1M", "status=progress", "conv=fdatasync"]
                    subprocess.run(cmd)
            else:
                print("\n[!] Drive wiping cancelled: Confirmation keyword mismatch.")

        if clean_tmp:
            print("\n[+] Removing temporary diagnostic log files...")
            os.system("rm -f sgal_report_*.txt /tmp/sgal_drive_*.tmp")
            print(" -> Temporary log files deleted.")

# ==============================================================================
# 8. INTERACTIVE DASHBOARD (MAIN MENU)
# ==============================================================================

class SgalDashboard:
    def __init__(self):
        self.menu_items = [
            {"id": "A", "label": "CPU Stress Test (Forces 100% Multi-Core Load)", "type": "comp"},
            {"id": "B", "label": "RAM Memory Test (Allocates Physical RAM)", "type": "comp"},
            {"id": "GPU", "label": "GPU Stress Test (3D / OpenGL Rendering Pipeline)", "type": "comp"},
            {"id": "PULSE_OPT", "label": "Pulsing Load Mode (Pause/Resume Spikes)", "type": "pulse"},
        ]

        drives = StorageDetector.get_physical_drives()
        for d in drives:
            self.menu_items.append({"id": d["id"], "label": f"Drive Test: {d['name']}", "type": "drive"})

        self.menu_items.extend([
            {"id": "DUR_1", "label": "Short Stress Test (3 minutes)", "type": "duration"},
            {"id": "DUR_2", "label": "Medium Stress Test (10 minutes)", "type": "duration"},
            {"id": "DUR_3", "label": "Long Stress Test (20 minutes)", "type": "duration"},
            {"id": "DUR_4", "label": "Custom Duration (User specified)", "type": "duration"},
            {"id": "DUR_5", "label": "Infinite Stress Test (Until Ctrl+C)", "type": "duration"},
        ])

        self.menu_items.append({"id": "Z", "label": "Detailed Diagnostics (Real-time Metrics)", "type": "mode"})

        self.cursor_idx = 0
        self.selected = set()
        self.selected_duration = "DUR_1"
        self.pulse_on_sec = 8
        self.pulse_off_sec = 8

    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')

    def render(self):
        self.clear_screen()
        cores, ram_gb = HardwareSensors.get_system_resources()
        bios_info = HardwareValidator.get_bios_and_microcode()
        
        print("================================================================================")
        print(" SUPERGAMESANDLEGO - HARDWARE DIAGNOSTICS & STRESS")
        print(f" System: {cores} Threads | {ram_gb} GB RAM | Microcode: {bios_info['microcode']}")
        print(f" BIOS: {bios_info['bios_vendor']} v{bios_info['bios_version']} ({bios_info['bios_date']})")
        print("================================================================================")
        print(" Navigation: [Tab / Arrow Keys] Move | [Spacebar] Select | [C] Cleanup Menu | [X] Start | [Q] Quit\n")

        current_type = None
        for idx, item in enumerate(self.menu_items):
            if item["type"] != current_type:
                current_type = item["type"]
                if current_type == "comp":
                    print("┌── [1] COMPONENT TESTS ───────────────────────────────────────────────────────┐")
                elif current_type == "pulse":
                    print("└──────────────────────────────────────────────────────────────────────────────┘")
                    print("\n┌── [2] LOAD STRESS BEHAVIOR ─────────────────────────────────────────────────┐")
                elif current_type == "drive":
                    print("└──────────────────────────────────────────────────────────────────────────────┘")
                    print("\n┌── [3] DETECTED STORAGE DRIVES (INDIVIDUAL TESTS) ────────────────────────────┐")
                elif current_type == "duration":
                    print("└──────────────────────────────────────────────────────────────────────────────┘")
                    print("\n┌── [4] TEST DURATION ─────────────────────────────────────────────────────────┐")
                elif current_type == "mode":
                    print("└──────────────────────────────────────────────────────────────────────────────┘")
                    print("\n┌── [5] DIAGNOSTICS MODE ──────────────────────────────────────────────────────┐")

            cursor = ">" if idx == self.cursor_idx else " "
            mark = "(*)" if item["type"] == "duration" and item["id"] == self.selected_duration else ("[*]" if item["id"] in self.selected else "[ ]")
            label = item["label"]
            
            if item["id"] == "PULSE_OPT" and "PULSE_OPT" in self.selected:
                label += f" ({self.pulse_on_sec}s HEAVY / {self.pulse_off_sec}s LIGHT)"

            print(f"│ {cursor} {mark} {label:<68} │")

        print("└──────────────────────────────────────────────────────────────────────────────┘")
        print("┌── [6] ACTIONS ───────────────────────────────────────────────────────────────┐")
        print("│   [X] START DIAGNOSTICS                                                       │")
        print("│   [C] OPEN CLEANUP & DOWNLOAD MENU                                            │")
        print("│   [Q] EXIT                                                                    │")
        print("└──────────────────────────────────────────────────────────────────────────────┘")

    def configure_pulse_interval(self):
        self.clear_screen()
        print("================================================================================")
        print(" CONFIGURE INSTANT PAUSE/RESUME PULSE INTERVALS")
        print("================================================================================")
        try:
            on_val = input(" Enter Heavy-Load Duration in seconds [Default: 8]: ").strip()
            self.pulse_on_sec = int(on_val) if on_val.isdigit() else 8

            off_val = input(" Enter Pause / Idle Duration in seconds [Default: 8]: ").strip()
            self.pulse_off_sec = int(off_val) if off_val.isdigit() else 8
        except Exception:
            self.pulse_on_sec, self.pulse_off_sec = 8, 8

    def run_diagnostics(self):
        print("\n[SYSTEM] Starting selected diagnostics...")
        is_pulsing = "PULSE_OPT" in self.selected
        stress = StressEngine(
            targets=self.selected, 
            pulsing=is_pulsing, 
            pulse_on_sec=self.pulse_on_sec, 
            pulse_off_sec=self.pulse_off_sec
        )

        duration_seconds = None
        if self.selected_duration == "DUR_1":
            duration_seconds = 3 * 60
        elif self.selected_duration == "DUR_2":
            duration_seconds = 10 * 60
        elif self.selected_duration == "DUR_3":
            duration_seconds = 20 * 60
        elif self.selected_duration == "DUR_4":
            try:
                val = input(" Enter custom test duration in minutes: ").strip()
                duration_seconds = int(val) * 60
            except Exception:
                duration_seconds = 3 * 60

        stress.start()
        logger = DiagnosticLogger() if "Z" in self.selected else None

        print(f"\n[SYSTEM] Diagnostics running... (Duration: {duration_seconds // 60 if duration_seconds else 'Infinite'} min) (Press Ctrl+C to stop)")
        interval = 1
        start_time = time.time()

        try:
            while True:
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    print("\n[SYSTEM] Selected test duration reached. Stopping diagnostics...")
                    break

                time.sleep(1)
                live_temps = HardwareSensors.get_all_temperatures()
                fan_speeds = FanSensors.get_fan_speeds()

                print(f"--- Metric Measurement {interval} [{stress.pulse_state}] ---")
                if live_temps:
                    for comp, temp in live_temps.items():
                        print(f"  [TEMP] {comp:<35}: {temp}°C")
                else:
                    print("  [TEMP] No temperature sensors detected.")

                if fan_speeds:
                    for fan, rpm in fan_speeds.items():
                        print(f"  [FAN]  {fan:<35}: {rpm} RPM")

                if logger and live_temps:
                    logger.log_snapshot(live_temps)

                interval += 1

        except KeyboardInterrupt:
            print("\n[SYSTEM] Diagnostics interrupted by user.")
        finally:
            stress.stop_all()

        if logger:
            logger.save_file()

        print("\nPress any key to return to the main menu...")
        get_key()

    def run(self):
        while True:
            self.render()
            key = get_key()

            if key in ['DOWN', 'TAB']:
                self.cursor_idx = (self.cursor_idx + 1) % len(self.menu_items)
            elif key in ['UP', 'SHIFT_TAB']:
                self.cursor_idx = (self.cursor_idx - 1) % len(self.menu_items)
            elif key == 'SPACE':
                item = self.menu_items[self.cursor_idx]
                if item["type"] == "duration":
                    self.selected_duration = item["id"]
                else:
                    if item["id"] in self.selected:
                        self.selected.remove(item["id"])
                    else:
                        self.selected.add(item["id"])
                        if item["id"] == "PULSE_OPT":
                            self.configure_pulse_interval()
            elif key == 'C':
                cleanup_menu = CleanupDownloadMenu()
                cleanup_menu.run()
            elif key == 'X':
                self.run_diagnostics()
            elif key in ['Q', 'ESC']:
                print("\n[SYSTEM] Exiting application...")
                break

if __name__ == "__main__":
    DependencyChecker.check_and_prompt()
    app = SgalDashboard()
    app.run()
