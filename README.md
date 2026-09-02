# linux_stresstest_app
a linux stresstest app IN BETA


# 🚀 SUPERGAMESANDLEGO - Hardware Diagnostics & Stress Framework

An interactive Terminal User Interface (TUI) for Linux and WSL to stress-test your CPU, RAM, GPU, and Storage drives while logging real-time temperature and performance statistics.

---
use 'supergamesandlego' for the menu

## 📋 System Requirements

To ensure the application can stress your hardware to 100% and read all temperature sensors correctly, the following applications and tools are required:

1. **Python 3**: Runtime environment for the diagnostic dashboard.
2. **stress-ng**: Advanced workload generator for stressing CPU and RAM.
3. **glmark2**: OpenGL benchmark tool for GPU stress testing.
4. install opengl , python3 and stressng with this command
   
   sudo apt update && sudo apt install -y python3 stress-ng glmark2
   
6. **Nvidia Drivers / Telemetry (Optional)**: Provides `nvidia-smi` for GPU temperature tracking, command below.

   sudo apt install -y nvidia-utils-535

---

## ⚙️ Installation & Uninstallation Guide

### Option 1: Install & Remove the Application

**Install Application (System-Wide)**

curl -sSL [https://raw.githubusercontent.com/SuperGamesAndLego/linux_stresstest_app/main/supergamesandlego.py](https://raw.githubusercontent.com/SuperGamesAndLego/linux_stresstest_app/main/supergamesandlego.py) | sudo tee /usr/local/bin/supergamesandlego > /dev/null && sudo chmod +x /usr/local/bin/supergamesandlego


Bash
# Remove the global binary
sudo rm -f /usr/local/bin/supergamesandlego

# Remove generated diagnostic log reports
rm -f sgal_report_*.txt
