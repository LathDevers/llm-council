Solid review overall — but it's about 60/40 right, and one of its "corrections" is wrong for our actual config. Verdicts, checked against the handover doc and the files on disk:

Where the council is right

§1 — the ptpd hole is real, and worse than they say. Line 192 of the handover is the row linuxptp specifically | ptpd 2.3.1 ... on the lidar, and Phase 6 established the lidar's stock firmware can't do 1588v2 at all. So that row is justified by a test that couldn't have passed. ptpd has never been run against a camera. I also had this wrong in my own notes — one of my memory files asserts the cameras "fail against both ptp4l and ptpd," which is an extrapolation from the lidar test with nothing behind it. Both need correcting. /usr/sbin/ptpd is installed, so this is a 10-minute test.

§3 — the ppb/ppm error is real. The raw log at line 131 is freq +15508817, and ptp4l logs ppb, so that's ~15,509 ppm = 1.55%, not 15.5 ppm. That matters because it's the whole argument that killed the i40e frequency theory: "ptp4l needs only +15.5 ppm where phc2sys reported +100,027,000 ppb." Corrected, that's 1.55% vs 10% — both enormous, and still disagreeing by 6.4× on the same PHC. That argument is dead; the theory isn't as buried as the doc says.

Packet bookkeeping — agreed, -c 120 can't yield 437 packets, and 91 Syncs at 1/s isn't 24 s either. Doesn't touch the conclusion (the 105/105 pairing ratio is the point), but the numbers are mush.

Lidar 3 ms ≠ forced asCapable — agreed, and it's the right instinct. Forced asCapable means an assumed path delay of zero; on direct copper that's a single-digit-µs error. It cannot produce 3 ms. Pipeline latency is the better explanation and it does strengthen the RoboSense ticket.

Where they're wrong

§3, operLogSyncInterval. Their fix is already in the file. gPTP-daisy.cfg has logSyncInterval -3 on line 13 (inherited from stock gPTP.cfg) and operLogSyncInterval -3 on line 7. The standard knob was never unset — so "you used the automotive-only option" doesn't explain anything. The wire still showing ~1 Sync/s with both set to -3 is still unexplained, and the council's answer would have sent you off believing it was fixed.

Their caveat on the −0.4 ppm measurement. They warn it may have canceled out the increment error "if it relied on hardware RX timestamps from the same i40e PHC." Default tcpdump/libpcap doesn't enable hardware timestamping — you get software timestamps off CLOCK_REALTIME. So that measurement compared PHC-stamped Follow_Up payloads against an independent reference, and it stands: the served timebase is sub-ppm regardless of what the raw increment is doing. The served time is still exonerated; only the "cosmetic read-back artifact" explanation lost its support.

H2 (OUI gating) is a long shot dressed up as a peer. Cheap enough to run, but it's a guess with no evidence behind it. H3 is checkable but not from anything we have — no pcaps were saved anywhere in the tree, so any field diff needs fresh captures on both sides.

H1 is the good one, and it's testable right now

Their epoch/step-saturation hypothesis is the only one that explains the shape of the failure — a >2 ms residual that never converges — and it fits the no-RTC observation. It also collides with something already in my notes: ptpTimeText was read as real UTC (2 h behind CEST) on 2026-09-03, which would mean the camera did absorb a 56-year step at some point. If that reading holds during a failing run, H1 dies immediately; if it reads 1970, H1 is the answer.

Their step 1 and H1 are the same measurement, and cam 1's leg is up right now (enp65s0f1np1, 192.168.3.1).

One step: read the camera's own clock at three points — PTP off, then ptp4lera at Uncalibrated, plus ptpStatus/ptpServoStatus alongside. Via theharvesters/Spinnaker GenTL path, keyed on id_ = "00010DC810A1". I'd verify the node names off the node map first (ptpTimeText we know exists; timestampControlLatch/timestampValue are the Sapera spelling and should be confirmed rather than assumed).