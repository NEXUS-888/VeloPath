VeloPath GPU Worker - lends this laptop's NVIDIA GPU to a friend's VeloPath app.

ONE-TIME SETUP
1. Update the NVIDIA driver: https://www.nvidia.com/drivers (or the NVIDIA app).
2. Install Tailscale: https://tailscale.com/download . Sign in and accept the invite
   from your friend, so both laptops are on the same private Tailscale network.
3. Unzip this folder anywhere (e.g. Desktop\velopath_gpu_worker).

EACH TIME
1. Plug in the charger (the GPU runs slower on battery).
2. Make sure Tailscale is connected (its tray icon).
3. Double-click start_worker.bat.
   - First run downloads about 3 GB (Python, CUDA PyTorch). Later runs start in seconds.
   - If Windows Firewall asks, click "Allow".
4. When it shows "VeloPath GPU worker running", leave the window open.
   The laptop will not sleep while it runs. Close the window to stop.

SAFETY
- Only devices on your Tailscale network can reach it, and every request needs the
  secret key in key.txt. Do not share key.txt with anyone else.
- It only runs ball tracking on video clips it is sent and returns trajectory points; it cannot read your personal files.
