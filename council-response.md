This is an exceptionally well-written, rigorous, and highly actionable handover. The fault-stacking framing, the strict reversal discipline (keeping disproven theories visible), and the clear isolation of variables are textbook engineering.

The council has reviewed your investigation. We agree that the architectural takeaway—camera-as-grandmaster as the fallback, RoboSense ticket for the lidar’s 802.1AS conformance—is sound. However, we have identified **one critical logical gap in the "ruled out" table, one major unit-math error**, and **three new hypotheses** that better fit the evidence than a simple packet field mismatch.

Here is our consolidated peer review and an upgraded action plan.

## 1. A Critical Hole in the "Ruled Out" Table

> "linuxptp specifically — `ptpd 2.3.1` as an independent master produced the same complete-exchange-no-sync on the lidar."

**This test is invalid by construction.** Phase 6 established that the lidar’s stock firmware cannot perform 1588v2 at all. Therefore, `ptpd` never stood a chance of syncing the lidar. Because of this, **`ptpd` has never actually been tested against the cameras.**

The hypothesis that the Nano-5G specifically rejects `linuxptp` (or non-Teledyne masters) is still completely open.

- **Immediate Action**: Run `ptpd` as master against Camera 1. If it locks, you know the issue is `linuxptp`’s specific packet layout. If it fails, the issue is likely vendor-gating by the camera.

## 2. The Arithmetic Narrowing & Three New Hypotheses

A computed offset of >2 ms on a direct link with a 131 µs RTT and −0.4 ppm drift is not a tuning problem; it is a grossly wrong mathematical input. The formula is `offset = (t2 − t1) − meanPathDelay`. Because `t2` and `t3` (the camera's own timestamps) are proven good by the 16-second camera-to-camera lock, the camera must be **mis-extracting or gating `t1` or `t4`** from the host packets.

Here are the highest-probability causes, ranked:

**H1: The Epoch / Step-Magnitude Limit (Architectural)**

Every working pairing in your document has one thing in common: the master's absolute time is close to the slave's starting time. You noted the camera has no RTC (`ptpMode` doesn't survive a power cycle).

- **Camera ↔ Camera:** Both boot near epoch zero, so the initial offset between them is small.
- **Host as Slave:** `linuxptp` can step a clock by 56 years without issue.
- **Host as Master:** The host serves UTC 2026. The camera boots at epoch zero. If the camera’s servo logic has a capped step magnitude (e.g., a 32-bit nanosecond limit), it will attempt to step, find itself still >2 ms off, unlock, and loop forever.
- **Test:** Set the host PHC to `0` (or check what absolute time the camera master served in the phase 7 captures) and run `ptp4l`. If it locks, this is an epoch-step saturation bug.

**H2: OUI / clockIdentity Gating (Vendor Lock-in)**

The Teledyne manual explicitly assumes *"only Nano-5G cameras are used."* The camera might silently gate timestamps if the master's `clockIdentity` does not contain the Teledyne OUI (`00:01:0D`).

- **Test:** Spoof the host NIC MAC to `00:01:0D:FF:FE:xx:xx` and run `ptp4l`. This is a 10-minute binary test.

**H3: Two-Step `Sync.originTimestamp` Misread (Protocol)**

In two-step mode, `linuxptp` leaves the `Sync.originTimestamp` unpopulated (zeroed). A device that follows the standard correctly ignores this field and waits for `Follow_Up`. However, embedded cameras often populate it anyway with an estimate. If the Nano-5G slave parser *demands* a value there (or adds it to the `Follow_Up`), reading `linuxptp`'s zeros will result in garbage math.

## 3. Corrections to Document Math & Assumptions

- **The i40e +10% Artifact is 1.55%, not 15.5 ppm:** You noted `freq +15508817` and called it "+15.5 ppm." **`ptp4l` logs frequency in ppb**. 15,508,817 ppb is ~15,509 ppm, which is **1.55%**. That is a massive clock drift. If your −0.4 ppm on-wire measurement relied on hardware RX timestamps from the same i40e PHC, the increment error canceled out. Keep this in mind when you reach Step 5 (`ts2phc`).
- **`operLogSyncInterval` did not take effect because it can't:** In `linuxptp`, this option is only consumed on the *automotive profile* code path. For standard profiles, the knob is `logSyncInterval`.
- **Fault 4 Mechanism:** Your original script used `-S` on both legs, meaning both `ptp4l` instances served `CLOCK_REALTIME`. The `phc2sys` on the camera leg was therefore disciplining a PHC that nothing was reading. (Your conclusion stands, but the mechanism wording was slightly off).
- **Lidar ~3 ms offset is NOT the forced `asCapable`:** Forcing `asCapable` assumes a neighbour propagation delay of zero. On a direct copper link, the true delay is single-digit microseconds. A microsecond error cannot explain a 3-millisecond offset. That 3 ms is likely uncompensated internal scan/pipeline latency in the lidar, which strengthens your RoboSense 802.1AS conformance ticket.
- **Packet count typo:** "120-packet capture" is followed by counts summing to 437. You likely meant a 120-second capture.

## 4. Upgraded Next Steps

We recommend reordering your next steps to execute the cheapest, highest-yield diagnostics first:

1. **The Missing Measurement (10 minutes):** You measured the wire and the host, but nobody has read the camera's internal notion of time. Use the GigE Vision node map (`timestampControlLatch` -> `timestampValue`) during a failing ptp4l run.
   - If it reads 1970/garbage: It is mis-extracting `t1`/`t4`.
   - If it reads 2026 but wanders: The servo is fighting a real mathematical error.
2. **The Cheap Falsifications (20 minutes):**
   - Run `ptpd 2.3.1` against the camera.
   - Spoof the host NIC MAC to the Teledyne OUI.
   - Set the host PHC to `0` and run `ptp4l`.
3. **The Upgraded Diff (Synthetic Bisection):** A visual packet diff shows correlation, not causation. Instead of just looking at Wireshark, use Python `scapy` to build a synthetic master that byte-mimics the working Camera Master. Once the slave locks to it, mutate one field at a time (`Sync.originTimestamp`, `correctionField`, TLVs, message length) toward `ptp4l`'s footprint. The exact field that breaks the lock is your definitive vendor bug report.
4. **Fallback Warning:** Your fallback architecture (Camera → Host PHC1 → CLOCK_REALTIME → Host PHC0 → Lidar) structurally recreates Fault 4 if you aren't careful. Ensure you use `phc2sys -a -r` and `-w` so the second hop strictly waits for the first to lock, enforcing directionality.