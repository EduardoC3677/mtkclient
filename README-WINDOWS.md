### Windows

#### Install python + git
- Install python >= 3.9 and git
- If you install python from microsoft store, "python setup.py install" will fail, but that step isn't required.
- WIN+R ```cmd```

#### Install Winfsp (for fuse)
Download and install [here](https://winfsp.dev/rel/)

#### Grab files and install
```shell
git clone https://github.com/bkerler/mtkclient
cd mtkclient
pip3 install -r requirements.txt
```

---

### USB Driver Setup: Zadig vs UsbDK

mtkclient uses **libusb** to communicate with MediaTek devices over USB. On Windows, you need a compatible USB driver installed. There are two options:

| | **Zadig (WinUSB)** | **UsbDK** |
|---|---|---|
| **How it works** | Replaces the device driver with WinUSB for a specific USB device | Installs a system-wide filter driver that works alongside existing drivers |
| **Best for** | CDC ACM preloader devices (e.g. Moto G05, MT6768) that get `[Errno 5] Input/Output Error` | BROM mode devices (VID `0x0E8D`, PID `0x0003`) that work without driver issues |
| **Pros** | Gives libusb direct endpoint access; fixes I/O errors on composite CDC ACM devices | No per-device setup needed; works automatically for all USB devices |
| **Cons** | Must be applied per-device; needs to be re-applied if Windows reassigns the driver | May not work with some CDC ACM composite devices; can conflict with other USB software |

**Recommendation:**
- **Try UsbDK first** — it's simpler and works for most devices.
- **Use Zadig** if you see `[Errno 5] Input/Output Error` or `[Errno 10060] Operation timed out` during handshake. This is common with CDC ACM preloader devices like **Moto G05/G15 (MT6768)**.

---

### Option A: Install Zadig (WinUSB) — Recommended for CDC ACM preloader devices

#### Step 1: Download Zadig
- Download Zadig from [https://zadig.akeo.ie/](https://zadig.akeo.ie/)
- Run `zadig-2.9.exe` (or latest version) — no installation needed, it's a portable executable

#### Step 2: Put your phone in preloader mode
- Power off your phone completely
- Hold **Vol Up** (or **Vol Down** depending on device) and connect the USB cable
- The phone should appear as a new USB device in Windows
- You only have a few seconds before the device disappears — be ready with Zadig open

#### Step 3: Install WinUSB driver with Zadig
1. In Zadig, go to **Options → List All Devices**
2. In the dropdown, find your MediaTek device. It will appear as one of:
   - `MediaTek PreLoader USB VCOM (Port)` or `USB CDC ACM` — for preloader mode (PID `0x2000`)
   - `MediaTek USB Port` — for BROM mode (PID `0x0003`)
3. Make sure the target driver (right side of the green arrow) shows **WinUSB (v6.x.xxxx.xxxxx)**
4. Click **Replace Driver** (or **Install Driver** if no driver is currently assigned)
5. Wait for the installation to complete (may take a minute)

> ⚠️ **Important for CDC ACM composite devices** (like Moto G05/MT6768):
>
> The device has 2 USB interfaces. You need to install WinUSB on **Interface 1 (CDC Data)**, which has the Bulk IN/OUT endpoints used for communication:
>
> 1. In Zadig, go to **Options → List All Devices**
> 2. Look for the entry that shows **(Interface 1)** in the name
> 3. Install WinUSB on that interface
> 4. If you only see one entry, install WinUSB on it — Zadig will handle the composite device
>
> You may also need to install WinUSB on **Interface 0 (CDC Communication)** if you still get errors.

#### Step 4: Verify the driver
- Open **Device Manager** (WIN+R → `devmgmt.msc`)
- Under **Universal Serial Bus devices**, you should see your MediaTek device with the WinUSB driver
- There should be **no yellow exclamation mark**
- Run mtkclient again — the `[Errno 5]` errors should be gone

#### Troubleshooting Zadig
- **Device not showing up in Zadig?** Make sure the phone is in preloader/BROM mode (power off, hold volume button, connect USB). Check **Options → List All Devices**.
- **Device disappears too quickly?** Preloader mode is only active for a few seconds. You may need to repeat: disconnect USB, hold volume button, reconnect while Zadig has "List All Devices" enabled.
- **Wrong driver installed?** In Zadig, select the device and click **Replace Driver** again with WinUSB selected.
- **Want to revert to original driver?** In Device Manager, right-click the device → **Uninstall device** → check **"Delete the driver software for this device"** → unplug and replug the phone.

---

### Option B: Install UsbDK — Simpler for BROM mode devices

- Install normal MTK Serial Port driver (or use default Windows COM Port one, make sure no exclamation is seen)
- Get usbdk installer (.msi) from [here](https://github.com/daynix/UsbDk/releases/) and install it
- Test on device connect using "UsbDkController -n" if you see a device with 0x0E8D 0x0003
- Works fine under Windows 10 and 11 :D

---

#### Building wheel issues (creds to @Oyoh-Edmond)
##### Download and Install the Build Tools:
    Go to the Visual Studio Build Tools [download](https://visualstudio.microsoft.com/visual-cpp-build-tools) page.
    Download the installer and run it.

###### Select the Necessary Workloads:
    In the installer, select the "Desktop development with C++" workload.
    Ensure that the "MSVC v142 - VS 2019 C++ x64/x86 build tools" (or later) component is selected.
    You can also check "Windows 10 SDK" if it’s not already selected.

###### Complete the Installation:
    Click on the "Install" button to begin the installation.
    Follow the prompts to complete the installation.
    Restart your computer if required.