**The Council recognizes the corrections.** You have successfully caught two of our analytical misses, isolated an error in your own notes, and collapsed a sprawling diagnostic tree into a single, highly falsifiable 10-minute test. 

Here is the adjudicated state of the board, followed by the exact execution protocol to run on the live link.

### 1. The Board is Cleaned (Adjudications)

**Retracted: The `operLogSyncInterval` configuration.** 
You are entirely correct. With both `-3` knobs present in your `gPTP-daisy.cfg`, our explanation for the 1 Hz wire rate was invalid. However, consider a critical architectural detail: the Teledyne Nano-5G is a standard IEEE 1588v2 (UDP/IPv4, End-to-End) device, not an 802.1AS (L2, Peer-to-Peer) device. 
*Are you certain `ptp4l` actually used the gPTP config on the camera leg?* If `ptp4l` was run with standard defaults (or fell back due to profile mismatch), the default `logSyncInterval` is `0` (1 Hz). Before assuming a camera-side negotiated override, check your bash history or `ps aux` to confirm the exact `argv` on the wire.

**Retracted: The timestamp-cancellation caveat.**
Your measurement stands. Because default `tcpdump` uses software timestamps (`SOF_TIMESTAMPING_SOFTWARE`) referenced to `CLOCK_REALTIME`, the independent on-wire measurement of \u22120.4 ppm is completely decoupled from the i40e PHC hardware increment bug. The served timebase is fully exonerated. (That said, 1.55% vs 10% is still a 6.4\u00d7 internal hardware disagreement on that PHC. Bookmark that hardware pathology for Step 5, but it is no longer a suspect for the camera sync failure).

**Conceded: The `ptpd` gap.**
`ptpd` has never touched a camera. The "linuxptp-specific packet layout" hypothesis remains wide open.

### 2. The Epistemology of `ptpTimeText` & H1

Your note that `ptpTimeText` read real UTC (2026-09-03) is the most valuable clue we have, but **it does not automatically kill H1**. Its diagnostic value depends entirely on *when* it was read, and *how* the servo responds:

1. **Context Context:** If the reading occurred when the camera was acting as a Grandmaster, or if PTP was off but the camera retained time from a previous session, it tells us nothing about whether the slave path can cross the 1970 \u2192 2026 gap.
2. **The "Servo Re-lock Loop" Variant (H1'):** Even if the camera *does* absorb the 56-year step (so `ptpTimeText` correctly shows 2026), the servo logic might be incapable of holding it. If the math overflows in the fine-servo loop, the camera will step, overshoot, drop to `Uncalibrated`, reset, and oscillate indefinitely around a >2 ms residual. 

Because of this, a single glance at a coarse text string is not enough. You must poll the **raw, numeric nanosecond tick counter**, and you must poll it repeatedly during the actual failing run.

### 3. The 10-Minute Live Run (Execution Protocol)

Keep the host PHC and network configuration exactly as they are. Do not change the MAC or profile yet. Because GenICam namespaces vary wildly (SFNC `TimestampLatch` vs Sapera `timestampControlLatch`), the script below is written defensively to discover your specific nodes, latch them, and read them.

Save this as `cam_clock_poll.py` and run it on the host.

```python
from harvesters.core import Harvester
import time
import datetime

# --- CONFIGURATION ---
CTI_PATH = '/opt/spinnaker/lib/spinnaker-gentl/Spinnaker_GenTL.cti' # Verify path
TARGET_ID = '00010DC810A1'

def get_node_val(nm, *names):
    for name in names:
        if hasattr(nm, name):
            try:
                return getattr(nm, name).value
            except:
                pass
    return "<N/A>"

def execute_cmd(nm, *names):
    for name in names:
        if hasattr(nm, name):
            try:
                getattr(nm, name).execute()
                return True
            except:
                pass
    return False

def main():
    h = Harvester()
    h.add_file(CTI_PATH)
    h.update()
    
    print(f"Connecting to {TARGET_ID}...")
    ia = h.create({'id_': TARGET_ID})
    nm = ia.remote_device.node_map

    print("\n--- Live Polling Started ---")
    print("Press Ctrl+C to exit.\n")
    
    try:
        while True:
            # 1. Fire the latch command (required by GigE Vision standard before read)
            execute_cmd(nm, 'timestampControlLatch', 'TimestampLatch', 'GevTimestampControlLatch')
            
            # 2. Read states
            host_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            ptp_text = get_node_val(nm, 'ptpTimeText', 'PtpTimeText')
            raw_ns   = get_node_val(nm, 'timestampValue', 'TimestampValue', 'GevTimestampValue')
            status   = get_node_val(nm, 'ptpStatus', 'PtpStatus')
            servo    = get_node_val(nm, 'ptpServoStatus', 'PtpServoStatus')

            print(f"Host UTC    : {host_utc}")
            print(f"ptpTimeText : {ptp_text}")
            print(f"Raw Latch   : {raw_ns}")
            print(f"State       : Status=[{status}] | Servo=[{servo}]")
            print("-" * 40)
            
            time.sleep(1.5)
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ia.destroy()
        h.reset()

if __name__ == '__main__':
    main()
```

### 4. The 3-Point Procedure & Interpretation

Open two terminals. In Terminal A, run the Python script. In Terminal B, control the PTP daemons. 

**Step 1: The Baseline (PTP Off)**
Ensure `ptp4l` and `phc2sys` are completely stopped on this leg. Run the Python script. 
*Note whether the camera is sitting at 1970, or if it has retained 2026 from a previous run.*

**Step 2: The Failing State (PTP On)**
Start your failing `ptp4l` master configuration. Watch the Python script as `ptp4l` reports `Uncalibrated`.

| Observation during Failing State | Interpretation & Next Step |
| :--- | :--- |
| **Stays at ~1970** | **H1 (Strong) Confirmed.** The camera rejects the 56-year step entirely. <br>*Action:* Stop `ptp4l`, zero the host PHC (`phc_ctl /dev/ptpX set 0`), and restart `ptp4l`. If it locks, you have proven step-saturation. |
| **Reads 2026 but wanders by milliseconds** | **H1' (Servo-loop) Confirmed.** Epoch acquired, but fine-servo math blows up. <br>*Action:* Proceed to Step 3 (`ptpd`). |
| **Reads stable 2026, never crosses to Locked** | **H3 (Extraction/Math) Confirmed.** The camera is stable but incorrectly parsing `t1`/`t4` or the `correctionField`, leaving a static >2ms residual. <br>*Action:* Proceed to Step 3 (`ptpd`). |
| **`ptpTimeText` says 2026, Raw Latch says 1970** | **Clock Domain Decoupling.** The display text is an RTC/convenience node, but the actual imaging timestamp is uncorrected. Trust the Raw Latch. |

**Step 3: The `ptpd` Falsification (Parallel Test)**
If the clock reaches 2026 but wanders or fails to lock (ruling out the strong 1970-cap), kill `ptp4l` and instantly run `ptpd` in master mode on the same interface:
`sudo ptpd -M -i enp65s0f1np1 -C`

*   **If `ptpd` locks:** You have isolated the bug to `linuxptp`'s specific packet layout (likely H3: `linuxptp` zeroing out the two-step `originTimestamp`, which Teledyne's parser might strictly demand). You can confirm this later via Python `scapy` synthetic bisection.
*   **If `ptpd` fails identically:** The issue is structural to the camera firmware's math, or it is vendor-gating (H2). At this point, taking 10 minutes to spoof the host NIC MAC to the Teledyne OUI (`00:01:0D...`) is completely justified.