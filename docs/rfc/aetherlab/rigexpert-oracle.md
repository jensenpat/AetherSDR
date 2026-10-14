# RigExpert device-support implementation oracle

First target: **RigExpert Stick Pro over USB HID**, for the proposed **AetherLab** workspace in AetherSDR.

Compiled: **2026-10-14**. Oracle revision: **0.1 — source research**.
Published reference snapshot for the AetherLab RFC. The [offline reference bundle](./rigexpert-reference-bundle.zip) contains the complete source corpus, hash manifest, and consistency checker.

| Evidence item | Status |
|---|---|
| Official product specifications and manuals | Read; text extracts archived |
| Manufacturer AntScope2 source | Audited at pinned commit `901923c3029e661385fdf88dc7b089cc2263f609` |
| Source commit date | 2026-09-30 15:21:27 UTC |
| Source-declared AntScope2 version | 2.0.4 in `AntScope.pro`; not proof of the operator's installed version |
| AetherSDR integration survey | Local commit `ae699be2580cc6c89d6d56790db18ec497d9dc99`; no application changes |
| Source-derived byte/math checks | CRC table and illustrative vectors checked; §15 |
| Actual analyzer identity/firmware | **Not captured** |
| USB/BLE hardware measurements | **Not run** |
| AetherSDR build, application tests, bridge validation, RF validation | **Not run** |

This document is an implementation reference and validation plan. It is not a vendor ICD, a certification result, an approved architecture, or authority to contact hardware. Read §0 and §14 before implementing.

## Contents

- [0. Authority, scope, and evidence rules](#0-authority-scope-and-evidence-rules)
- [1. What is shared across RigExpert devices](#1-what-is-shared-across-rigexpert-devices)
- [2. Stick Pro limits and measurement topology](#2-stick-pro-limits-and-measurement-topology)
- [3. USB identity and report transport](#3-usb-identity-and-report-transport)
- [4. USB command vocabulary and sweep ordering](#4-usb-command-vocabulary-and-sweep-ordering)
- [5. Sweep count, completion, stop, and recovery](#5-sweep-count-completion-stop-and-recovery)
- [6. BLE protocol and variants](#6-ble-protocol-and-variants)
- [7. Modes and capability coverage](#7-modes-and-capability-coverage)
- [8. Measurement outputs and numerical behavior](#8-measurement-outputs-and-numerical-behavior)
- [9. Calibration and reference-plane ownership](#9-calibration-and-reference-plane-ownership)
- [10. Boundary validation and resource limits](#10-boundary-validation-and-resource-limits)
- [11. Files and reproducibility](#11-files-and-reproducibility)
- [12. Proposed AetherLab integration contract](#12-proposed-aetherlab-integration-contract)
- [13. Validation matrix and hardware experiments](#13-validation-matrix-and-hardware-experiments)
- [14. Minimum viable offering and exit gates](#14-minimum-viable-offering-and-exit-gates)
- [15. Reproducibility and update procedure](#15-reproducibility-and-update-procedure)
- [16. Questions that require hardware or vendor answers](#16-questions-that-require-hardware-or-vendor-answers)

## 0. Authority, scope, and evidence rules

### 0.1 Source precedence

1. **Model-specific official RigExpert documentation** for supported frequency range, physical port topology, and operating restrictions.
2. **Captures and measurements from the particular device**, identified by model, hardware revision, firmware, transport, OS, and test configuration. They qualify actual behavior for that tuple; they do not override published physical operating limits.
3. **RigExpert's public AntScope2 source at a pinned commit**, for client encodings, parsing, command order, and documented-by-implementation quirks.
4. HIDAPI/Qt's published API contracts for host transport behavior ([HIDAPI API header](https://github.com/libusb/hidapi/blob/master/hidapi/hidapi.h)).
5. Third-party implementations and this oracle.

A source conflict is recorded, investigated, and resolved for the target device. Do not silently choose a convenient interpretation.

Use these evidence labels:

| Label | Meaning |
|---|---|
| **D** | Manufacturer documentation states the fact |
| **S** | Manufacturer client source implements the behavior |
| **I** | Inference/calculation from identified evidence |
| **P** | Proposed AetherSDR implementation or test requirement |
| **H** | Demonstrated on identified hardware, with linked evidence |

**There are no H claims in revision 0.1.** A client-side workaround is S, not a firmware specification.

### 0.2 Clean sources and licensing

The protocol research uses public manufacturer source, public manuals, and mathematical derivation. It uses no decompiled or disassembled proprietary binaries.

AntScope2's root [MIT license][license] permits reuse subject to preservation of its notice. Review licenses of any bundled third-party component separately. The initial implementation should use AetherSDR's existing HIDAPI support, not vendor AntScope2's bundled HID library or entire application.

The snapshot is a **reference**, including legacy globals, UI coupling, permissive parsers, and model-specific workarounds. Copying it wholesale would import behavior that the oracle explicitly requires us to validate or improve.

### 0.3 Scope

- Implement first against the operator's **Stick Pro, USB HID, identified firmware**.
- Research BLE here, but leave it outside the first hardware qualification.
- Preserve extension points for later ZOOM/Stick models without advertising untested compatibility.
- Do not infer S21, firmware update, device calibration write, flash erase, or automatic RF switching support.
- The proposed tab UX and session integration remain design proposals. Repository RFC and review procedures remain in the canonical project files; this document does not replace them.

## 1. What is shared across RigExpert devices

**RigExpert has shared protocol families, not one identical protocol for every model.**

[S] AntScope2 selects separate adapters in [AnalyzerPro::createDevice](https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/analyzerpro.cpp#L779-L824):
USB HID, serial, NanoVNA, and BLE. The last is a separate manufacturer-client integration, not evidence that a NanoVNA speaks the RigExpert protocol.

| Layer | Shared behavior | Differences requiring qualification |
|---|---|---|
| Measurement semantics | Frequency plus resistance/reactance for basic reflection analysis | Range, accuracy, reference plane, calibration, extended fields |
| Text command vocabulary | FQ, SW, FRX, off; identity and saved-record commands | Supported commands, firmware parsing, count/endpoints |
| USB HID | Report wrapper around text commands/results on identified HID models | Descriptor/report size, serial/model recognition, firmware |
| Serial / Bluetooth serial | Text command flow through ComAnalyzer | Baud rate, CR/LF handling, AA-55 compressed output variant |
| BLE | GATT service, binary command frames, CRC-8 | Legacy float sample vs newer four-sample compressed frame |
| Device front panel | Antenna/cable tools with related names | A front-panel mode is not automatically a remotely addressable mode |

### 1.1 Candidate compatibility matrix

These are **source candidates**, not a release support list. Ranges below are AntScope2 model-table values, expressed in MHz after converting its kHz strings. A new target also needs its own official model reference.

| Candidate model | Source serial prefixes | Source range | Evidence / first implementation disposition |
|---|---|---|---|
| Stick Pro | 4600, 4601 | 0.1–600 | HID identity mapped; target USB qualification first |
| Stick 230 | 4230, 4231 | 0.1–230 | Same HID family is a candidate; not qualified |
| AA-35 ZOOM | 1350, 1351 | 0.06–35 | Model table + HID family candidate; not qualified |
| AA-55 ZOOM | 1550, 1551 | 0.06–55 | HID candidate; serial parser also has AA-55 firmware-dependent compressed format |
| AA-230 ZOOM | 1232 | 0.1–230 | HID candidate and explicit serial path; transport must be specified |
| AA-650 ZOOM | 1650 | 0.1–650 | HID family candidate; not qualified |
| AA-1500 ZOOM | 1015 | 0.1–1500 | HID family candidate; not qualified |
| AA-1500 ZOOM SE | 4115 | Separate profile required | Named identity; do not inherit the ordinary 1500 profile |
| Older serial AA models / AA-30 ZERO | Separate model mapping | Model-specific | ComAnalyzer path; not a Stick Pro adapter |
| Other/newer BLE models | Device-discovered identity | Model-specific | Same service may carry a different sample layout |

Sources: [model table][models], [identity mapping][identity], [serial adapter][serial].
Store a device profile as **model + revision + firmware + transport + protocol variant**, not “RigExpert supported = true.”

### 1.2 Concrete incompatibility example: AA-55 serial variant

[S] ComAnalyzer enables its newer AA-55 parser when the parsed three-character version is an integer greater than 125. That is **source-specific version parsing**, not a general semantic-version rule.

The newer path expects a 14-character hexadecimal record representing little-endian R, X, point ID, and CRC. It uses the compressed impedance conversion also seen in newer BLE data and can request a missing point with a z-prefixed command.

This differs from ordinary comma-separated frequency/R/X records. Even a shared FRX request does not guarantee the same response parser.

Do not transplant the AA55BTPacket CRC behavior: it passes a six-byte buffer to a helper that excludes the final byte, so the effective checksum coverage needs an independent capture. References: [ComAnalyzer][serial], [AA55BTPacket][aa55], [CRC helper][crc].

## 2. Stick Pro limits and measurement topology

### 2.1 Documented limits

[D] [Product specifications][product] and [datasheet][datasheet]:

| Property | Published value | Implementation consequence |
|---|---|---|
| Frequency | 100 kHz–600 MHz | Validate full requested span before any measurement command |
| Front-panel frequency entry | 1 kHz | Does not by itself prove USB synthesizer quantization |
| Measurement topology | One N-type measurement port | Reflection/complex impedance; no direct S21 |
| RF output into 50 Ω | −10 dBm | About 0.1 mW; measurement itself generates RF |
| Source waveform | Square, per product page | Harmonic content is relevant to measurement/environment limits |
| System impedance choices | 12.5, 25, 28, 37, 50, 75, 100, 150, 200, 300, 450, 600 Ω | Record Z0 explicitly; qualify device-setting effect |
| SWR displayed | 1–10 in chart modes; 1–100 numerically | Display limits are not raw transport/data limits |
| Published R / X range | R 0…10000 Ω; X −10000…10000 Ω | Expected range; out-of-range handling must retain quality information |
| Front-panel SWR chart | 100 points | Not proof of USB FRX argument or remote point maximum |
| USB / wireless | USB Type-C; BLE 4.2 | USB is HID here; BLE is a separate protocol |

The linked old manual states a **10 kHz minimum Free-mode span**. That front-panel constraint is not yet established as a remote sweep minimum.

No qualified accuracy tolerance, sweep-speed envelope, input-power rating, DC-input tolerance, or USB point maximum was established in this research. Keep those unresolved rather than inventing specifications.

### 2.2 Conflicting documentation

The live product page, older manual, datasheet, and model table differ on screen dimensions and operating temperature. Screen dimensions do not gate the antenna-analysis PoC. Use a conservative operating environment for bench work and obtain model/revision-specific limits before environmental qualification.

Do not use screen size, shared PID, or the word “ZOOM” as the sole protocol selector.

## 3. USB identity and report transport

### 3.1 Discovery

[S] [HID constants][hid-header], [device enumeration][identity]:

| Field | Source value |
|---|---|
| Normal USB VID:PID | 0483:A1DE |
| Bootloader VID:PID | 0483:A1DA |
| Stick Pro model-prefix variants | 4600 / 4601 |
| HID report marker / ID | 07 hex |
| Client API report buffer length | 64 bytes |

The VID/PID is shared with other RigExpert analyzers. Qualify a selected device using its complete USB serial, product information, and VER response.

The source's externalSerial() extracts five characters after a four-character prefix; preserve the full identity too. Never open the first matching VID/PID when more than one analyzer is attached.

[P] Enumerate without measuring. Treat bootloader identity as **unsupported operating mode**, not permission to flash or reset. A device already used by AntScope2 or another client must produce a clear busy/open error; do not steal it or open multiple command owners.

### 3.2 Report envelope

[S] [HidAnalyzer::sendCommand / sendData][hid]:

| API-buffer offset | Size | Contents |
|---|---:|---|
| 0 | 1 | 07 hex |
| 1 | 1 | ASCII payload byte count |
| 2… | count | Command/result payload bytes |
| Remaining buffer | remainder | Zero padding in outgoing command buffers |

Both write paths call hid_write with length 64. One allocates 65 bytes but still writes 64. The illustrated source envelope therefore has a **62-byte payload capacity at the API-buffer level**.

**HID descriptor capture is mandatory.** HIDAPI includes report-ID handling in its API contract; distinguish the device descriptor's data length, the API buffer length, and USB capture length. Do not silently “fix” 64 to 65, or strip a leading ID twice, without checking the actual descriptor and each OS backend.

[P] Use explicit byte packing. Check ASCII encoding, count, available capacity, full write result, and actual read length. A partial write is a transport error, not successful dispatch.

### 3.3 Reading and line assembly

[S] hidRead() reads at most 64 bytes, requires the 07 marker, consumes the declared payload count, appends text to an accumulator, and parses complete LF-terminated records. CR is stripped within a complete line. A record can span several reports; a report can contain several lines.

The pinned implementation clamps claimed payload length to actual read capacity. [P] For our strict parser, a declared count larger than available data is malformed; do not accept a truncated numeric prefix as a measurement.

The header declares INPUT_BUFFER_SIZE = 32768, but the inspected append path does not enforce that constant. This is not evidence of a firmware report/line limit.

### 3.4 Identity handshake

[S] On open, the HID adapter sends VER CRLF, then FULLINFO CRLF, and enters identity parsing. It recognizes model/version/revision plus selected tab-delimited MAC, SN, and LIC fields. It skips FULLINFO NAME so that the VER-derived version remains in use.

[P] Preserve the entire identity response and bounded unknown fields. Do not truncate firmware to three characters merely because upstream does. Do not equate LIC with measurement capability or issue license-writing commands.

There is no established calibrated-state or remote-point-limit query in the audited Stick Pro USB path. Optional FULLINFO fields must be learned from actual captures before becoming trusted capability fields.

## 4. USB command vocabulary and sweep ordering

### 4.1 Commands demonstrated in source

Exact terminators matter: identity is CRLF in the HID open path; sweep and stop commands are CR in the common controller.

| Command | Source purpose | First PoC |
|---|---|---|
| VER CRLF | Model / firmware / revision | Include |
| FULLINFO CRLF | Additional identity / metadata | Include, bounded optional fields |
| FQ<integer> CR | Sweep center, Hz | Include |
| SW<integer> CR | Full sweep width, Hz | Include |
| FRX<N> CR | Basic frequency/R/X measurement stream | Include after count qualification |
| off CR | Stop request | Include; completion/RF-stop evidence remains separate |
| EFRX<N> CR | Extended header + user fields | Deferred; model support unknown |
| FLASHH CR | List stored measurements | Deferred |
| FLASHFRX<slot> CR | Read stored measurement | Deferred |
| screenshot CR | Device screenshot | Deferred |
| FDB<N> CR | Other models' S21 measurement path | Unsupported for Stick Pro topology |
| RESET / bootloader commands / erase | Firmware/service operations | Exclude |
| CALFIVEKOHM | Separate service/calibration feature seen elsewhere | Exclude; not a supported Stick Pro OSL API |

References: [BaseAnalyzer][base], [HID parser][hid], [AnalyzerPro][adapter].
There is no source-established USB command here for invoking each front-panel application mode by name.

### 4.2 ACK-driven sweep setup

[S] BaseAnalyzer computes:

- widthHz = stopHz − startHz
- centerHz = startHz + integer(widthHz / 2)

It then sends FQ, waits for OK, sends SW, waits for OK, and sends FRX. A 10 ms timer advances the controller; it is **not a 10 ms firmware response guarantee**.

Illustrative 20 m request, derived from source, **not captured**:

~~~text
Host: FQ14175000\r
Device: OK<line ending>
Host: SW350000\r
Device: OK<line ending>
Host: FRX100\r
Device: frequency_MHz,R_ohm,X_ohm<line ending>
        ... additional samples ...
~~~

Here the requested range is 14.000–14.350 MHz. The FRX argument is shown as 100; §5 explains why that must not be labelled “exactly 100 returned samples” yet.

A source-derived FQ API report begins:

~~~text
07 0B 46 51 31 34 31 37 35 30 30 30 0D
~~~

Pad to the source's 64-byte API buffer. Complete synthetic vectors are in [source-derived-vectors.json](./source-derived-vectors.json).

### 4.3 Proposed transaction state machine

[P]

~~~mermaid
stateDiagram-v2
    [*] --> Disconnected
    Disconnected --> Identifying: operator selects device
    Identifying --> Idle: identity qualified
    Idle --> AwaitCenterAck: explicit sweep request
    AwaitCenterAck --> AwaitSpanAck: current transaction OK
    AwaitSpanAck --> Receiving: current transaction OK / FRX sent
    Receiving --> Complete: qualified sample/grid completion
    Complete --> Idle: final dataset published
    AwaitCenterAck --> Stopping: cancel / error / deadline
    AwaitSpanAck --> Stopping: cancel / error / deadline
    Receiving --> Stopping: cancel / error / deadline
    Stopping --> Idle: qualified recovery / fresh identity as needed
    Identifying --> Fault: mismatch / deadline
    Stopping --> Fault: no qualified recovery
    Fault --> Disconnected: close
~~~

Every command belongs to one session generation and one operation. ACK is untagged text, so serialization and stale-input draining matter. Duplicate/stale OK must not advance two setup stages. An ERROR in any stage terminates that operation with context.

Configure timers per device profile from measured timing. Do not reuse source timers as correctness timeouts.

## 5. Sweep count, completion, stop, and recovery

### 5.1 The endpoint issue

[S] For normal FRX, AnalyzerPro::on_newData emits a sample before testing its counter, starts at zero, and completes when the counter is greater than N−1. That path therefore emits **N+1 samples** before normal completion. Its calibration path uses a different threshold and can reach N+2 at that controller layer.

[I] The normal convention looks like N intervals with both endpoints, but client arithmetic alone does not establish the instrument's exact convention. Other paths reconstruct frequency using span/N; extended-data completion uses N+1.

**Blocking experiment H-02:** capture FRX requests for several small and ordinary N values, record every frequency and trailing line, and determine the exact count/grid convention for this firmware.

- Separate requested UI sample count, wire argument, received samples, valid samples, and intervals.
- Do not copy the mockup's “201 points” literally into FRX201 without qualification.
- Preserve the device-returned frequency. Do not substitute an ideal grid merely to make a trace look complete.
- Do not infer maximum USB N from the front-panel chart's 100 points.
- AntScope2's ordinary global cap is 2000; it is **a client default**, not a qualified Stick Pro firmware maximum.

### 5.2 Completion

[S] Normal USB measurement completion is count-driven in AnalyzerPro; BaseAnalyzer's completion callback changes local state and does not itself send off. The HID parser handles OK as a generic ACK and ERROR as a log event; no distinct successful-sweep trailer is established here.

[P] A complete dataset needs a qualified count, expected grid/endpoints, valid ordered records, and a completed operation. A stall, parse failure, cancel, unplug, or timeout yields a partial/error dataset, never successful completion.

Without wire sequence IDs, local generations cannot identify all late bytes from a prior sweep. Stop/drain/re-identification must establish a clean operation boundary; this is a hardware qualification requirement.

### 5.3 Stop and disconnect

[S] The common USB stop method sends off CR and changes the local measuring flag. That proves a **stop request**, not device acceptance or RF silence. The HID override visible in the file is commented out; the common BaseAnalyzer implementation is the active path.

[P] Cancel during either ACK stage must stop the setup timer and prevent later FRX dispatch. Purge pending measurement intent. Drop late data from the retired operation while retaining it in bounded diagnostics if needed.

Treat three outcomes separately:

1. Acquisition stopped locally.
2. Device stop accepted / device idle established.
3. RF output actually ceased, if that is a claimed behavior.

The maximum residual RF duration and whether RF continues after natural completion, off, host close, cable unplug, or failed transport are unqualified.

### 5.4 Repeat and single-frequency mode

[S] Repeat sweeps are coordinated by the client. Single-frequency mode uses start = stop and upstream requests a very large count (100000). That is not a recommended PoC command or a safe documented firmware bound.

[P] Defer both until bounded acquisition, stop, and session fencing are qualified. If added, repeat starts only from explicit operator intent, has bounded history, and never automatically resumes after reconnect.

## 6. BLE protocol and variants

**BLE is researched for later support; it is not part of the first USB support claim.**

### 6.1 GATT discovery

[S] [BLE header][ble-header] and [implementation][ble]:

| Role | UUID |
|---|---|
| Service | D973F2E0-B19E-11E2-9E96-0800200C9A66 |
| Device notification/read | 706E4F15-3EE6-41C6-BA10-CA8ABDCF3043 |
| Host command write | 6F8963A8-21E9-4055-86B8-2F911D736CFF |
| Optional return-CRC write | 07395738-5D8A-11EC-BF63-0242AC130002 |
| Notification descriptor | 00002902-0000-1000-8000-00805F9B34FB |

The source enables notifications by writing 0100 hex to the descriptor. Presence of the optional return characteristic selects m_reuChip and a different sample format. Discover properties and complete subscription before announcing a ready session.

An older official manual says desktop BLE is unavailable, while the pinned source includes desktop BLE and platform support checks. This is a documentation/version mismatch, not proof of working BLE on this device or OS.

### 6.2 Common 20-byte packet

[S] Byte 0 is command type; bytes 1–18 contain command-specific data/padding; byte 19 is CRC-8 over bytes 0–18. Response streams use little-endian numeric fields and single-precision float decoding.

[I] The table matches **CRC-8 polynomial 07, init 00, no reflection, xorout 00**. Independent standard check: ASCII 123456789 gives F4. The helper excludes its final input byte, so provide a 20-byte packet with the last CRC byte excluded from coverage.

| Code hex | Source name | Use |
|---|---|---|
| E6 | VER | Declared identity command; support qualification needed |
| 9B | FULLINFO | Multi-field identity/capability responses |
| 7F | FRX | Sweep request / live measurement responses |
| 5A | PING | Liveness |
| 69 | BREAK | Stop request |
| 8F | REC_LIST | Stored-measurement listing |
| 9F | REC_DATA | Stored-measurement retrieval |
| AF | REC_ERASE | Destructive; exclude from PoC |
| AD | SCREENSHOT | Deferred |
| DA / D2 / D3 / E5 | Palette variants | Deferred |

### 6.3 Sweep request layout

[S] The source truncates start/stop Hz to integer kHz, computes center and span, appends native int bytes, pads to 20, and calculates CRC.

[P] Encode explicit little-endian int32 fields; do not serialize native memory.

| Offset | Size | Field |
|---|---:|---|
| 0 | 1 | 7F |
| 1 | 4 | center frequency, kHz, int32 LE |
| 5 | 4 | full span, kHz, int32 LE |
| 9 | 4 | FRX count argument, int32 LE |
| 13 | 6 | Zero padding |
| 19 | 1 | CRC-8 |

Source-derived request for center 14175 kHz, span 350 kHz, N = 100:

~~~text
7F 5F 37 00 00 5E 01 00 00 64 00 00 00 00 00 00 00 00 00 7A
~~~

The actual synthesized endpoints can differ after integer kHz truncation and midpoint rounding. Report requested and effective range separately; measure rounding on hardware.

### 6.4 Legacy response format

[S] Used when the optional return characteristic is absent:

| Offset | Size | Field |
|---|---:|---|
| 0 | 1 | 7F |
| 1 | 8 | Frequency Hz, uint64 LE |
| 9 | 4 | R Ω, float32 LE |
| 13 | 4 | X Ω, float32 LE |
| 17 | 2 | Count/index, int16 LE; semantic meaning unqualified |
| 19 | 1 | CRC |

Upstream converts frequency to float MHz and ignores the count in sample delivery. [P] Preserve integer Hz and inspect the count for sequencing after capture; avoid float precision loss.

### 6.5 Newer compressed response format

[S] Selected by return-characteristic presence:

| Offset | Size | Field |
|---|---:|---|
| 0 | 1 | 7F |
| 1 | 2 | Base sample ID, int16 LE |
| 3 | 16 | Four successive pairs of packed R uint16 / X uint16 |
| 19 | 1 | CRC |

For each packed 16-bit impedance value:

~~~text
mantissa = bits 0..12
decimalExponent = bits 13..14
negative = bit 15
ohms = mantissa × 123 / 10^(decimalExponent + 2)
apply sign if negative
~~~

[I] Four step sizes are 1.23, 0.123, 0.0123, and 0.00123 Ω; largest magnitude is 10074.93 Ω. These are encoding properties, not an accuracy specification.

[S] Upstream reconstructs frequency from the saved request, span/N, and packet index. It decrements an odd base ID and drops pairs where both packed values are zero. Treat these as source workarounds requiring hardware evidence; a zero pair must not be confused with a genuine short-circuit result without qualification.

### 6.6 CRC return, scheduling, capabilities

[S] On the newer variant the source returns the received CRC byte through the optional return characteristic. It serializes/defer-queues FRX while waiting for ping and suppresses pings during FRX.

FULLINFO includes subtypes for name, flags, measurement bounds/maximum points, serial/version, MCU, display, flash, and hardware string. The measurer subtype parses uint32 minimum, uint32 maximum, int8 extra multiplier, uint16 max points. The source displays bounds using 10^(3−extraMultiplier) with a kHz label. Capture the raw tuple before treating that conversion as a universal unit rule.

Source timer values include a 1 s liveness tick, 3 s ping constant, and a 900 ms no-FRX heuristic. The latter can emit “complete” on lost data. **Do not copy timeout-as-success.**

[P] Bound queues; validate packet length before indexing; validate CRC before callbacks; validate all stream extraction statuses; fence connection generations; require complete sample coverage. Qualify optional-characteristic ACK timing and retransmission behavior separately.

## 7. Modes and capability coverage

The first remote API is **basic impedance acquisition**. SWR, return loss, Smith chart, and other views can use the same samples. They do not need different firmware modes.

[D] Official material names these on-device tools:

| Front-panel tool | Meaning for AetherLab | Remote support disposition |
|---|---|---|
| Single | Scalar impedance/match at one frequency | Basic FRX acquisition exists; bounded zero-span qualification deferred |
| HAM | Preset-band SWR sweep | Host band-plan preset + qualified FRX |
| Free | User-range sweep | Core PoC |
| Multé | Multi-band antenna survey | Later host orchestration; native algorithm/command not established |
| Bound | Threshold check | Later host comparison of a qualified measurement |
| R&X | Impedance chart | Core view from FRX |
| RLoss | Return-loss chart | Derived from FRX |
| TDR | Distance-to-fault | Later qualified transform; not assumed native remote result |
| StubT | Stub tuning | Later analysis; algorithm/remote command unqualified |
| cLen | Cable length | Later analysis |
| cImp | Cable impedance | Later analysis |
| cLoss | Cable-loss estimate | Later one-port method with stated termination assumptions |

Sources: [manual][manual], [datasheet][datasheet], [measurement processing][measurements].

A one-port cable-loss estimate is not direct S21 insertion loss. Front-panel modes and generic client commands are separate capability surfaces.

Other source features—EFRX user columns, S21/FDB, firmware update, license operations, saved slots, screen capture—must each be gated by model/transport/firmware evidence. Shared class methods are not proof that Stick Pro implements them.

## 8. Measurement outputs and numerical behavior

### 8.1 Authoritative primitive

[S] USB FRX parsing yields frequency in the client's **MHz convention**, R Ω, and signed X Ω. This unit is supported by the shared RawData path, MHz file headers, and plot conversion to kHz. Verify it in the first capture.

[P] Normalize frequency once at the transport boundary into integer Hz, using a documented rounding rule; retain original token/frequency for diagnostics. Internal samples should carry:

- Frequency Hz, R Ω, X Ω.
- Session generation / acquisition ID and sample index.
- Per-sample validity or range flags.
- Device/firmware/transport identity through dataset metadata.
- Acquisition time and completeness status.

The ordinary USB payload has no source-established per-sample timestamp or wire acquisition ID. Local arrival time is not instrument measurement time.

### 8.2 Derived quantities

[P/I] For real positive reference impedance Z0 and Z = R + jX:

~~~text
Γ = (Z − Z0) / (Z + Z0)
|Z| = hypot(R, X)
impedance phase = atan2(X, R)
reflection phase = atan2(Im Γ, Re Γ)
SWR = (1 + |Γ|) / (1 − |Γ|), for 0 ≤ |Γ| < 1
return loss dB = −20 log10(|Γ|)
~~~

Impedance phase and reflection phase must have distinct labels. Smith-chart coordinates are Re Γ / Im Γ; normalized impedance is Z/Z0.

Optional equivalent series L = X/(2πf) for inductive X, and C = −1/(2πfX) for capacitive X. These are local equivalents at that frequency, not a measured physical component or a broadband matching solution.

| Ideal input, Z0 = 50 Ω | Γ | SWR | Return loss |
|---|---|---:|---:|
| 50 + j0 Ω | 0 | 1 | +∞ |
| 100 + j0 Ω | +1/3 | 2 | 9.542425 dB |
| 25 + j0 Ω | −1/3 | 2 | 9.542425 dB |
| 54 + j0 Ω | 1/26 | 1.08 | 28.299467 dB |
| 50 + j50 Ω | 0.2 + j0.4 | 2.618034 | 6.989700 dB |
| Ideal short | −1 | +∞ | 0 dB |
| Ideal open limit | +1 | +∞ | 0 dB |

These are **mathematical fixtures**, not required instrument readings or published accuracy limits.

### 8.3 Edge cases

[P]

- Exact match has undefined reflection phase and infinite ideal return loss. Represent this explicitly; do not fail the entire sample.
- Open/short approach |Γ| = 1 and unbounded SWR. Display an over-range indication without replacing the raw impedance.
- Noise can produce slightly nonphysical results. Flag them; do not hide them by substituting the previous sample.
- Reject NaN/Inf numeric input and undefined denominator operations; preserve meaningful finite raw samples with a quality flag.
- A plot may clip its y-axis; exports and saved raw data must not inherit clipping.
- The source's R floor, SWR cap, corrected Γ clipping, and fallback-to-previous-result are display/robustness choices, not measurement truth.

Reference: [Measurements::computeSWR / processing][measurements]. The mathematics here is independently derived; upstream display edge cases are not normative.

### 8.4 Minima, resonance, bandwidth

[P] Minimum SWR and X = 0 resonance are separate findings. Multiple resonances and multiple below-threshold intervals are possible.

Compute bandwidth only within a complete qualified sweep; interpolate threshold crossings using an explicit method and mark sweep-edge truncation. A sampled minimum is resolution-limited. A coarse scan cannot guarantee finding a narrow resonance.

Record source grid spacing, interpolation method, and whether the reported minimum/crossing is sampled or estimated.

## 9. Calibration and reference-plane ownership

### 9.1 Three correction layers

1. **Factory instrument calibration** — manufacturer states this exists.
2. **On-device user OSL correction** — manual describes its activation and front-panel C indicator.
3. **Host correction / cable compensation** — AntScope2 separately stores per-serial standards and applies calibration and cable transformations in Measurements.

[S] The host Calibration object loads open/short/load files, retains its own Z0, and can be enabled independently. Measurements keeps received and corrected arrays separately.

**Conclusion:** device-provided R/X makes a small PoC practical, but “all calibration is done on-device” is not established for every measurement path.

References: [official OSL instructions][manual], [Calibration][calibration], [received/corrected processing][measurements].

### 9.2 First implementation contract

[P]

- First capture compares AetherLab raw device R/X with AntScope2 **host OSL, cable add/subtract, and connector compensation disabled**.
- Device OSL setting is recorded and controlled manually for the experiment; restore it afterwards.
- Do not claim to read its state over USB until a documented/captured query exists.
- Calibration metadata can say **device OSL state unknown**. Operator-entered state is not a device-confirmed query result.
- Initially make no host correction. Preserve immutable device samples. Here “raw” means received R/X before host transformations; it does not mean uncalibrated detector/ADC samples.
- Do not apply a second correction to already-corrected data without explicit provenance and validation.
- Changing Z0 in the application recalculates reflection/match from Z; it does not recalibrate the instrument.
- Calibration performed at the analyzer connector does not automatically move the reference plane to the end of an added cable.

### 9.3 Required experiment

H-03 uses known loads and the same cable:

- Compare device OSL off/on, device front panel, raw USB output, and uncorrected AntScope2 exports.
- Repeat after power cycle and host reconnect.
- Repeat with a known extension cable and standards at its far end.
- Record Z0 and its setting changes; determine whether R/X itself changes.
- Decide whether the MVO can use device correction reliably, must report unknown correction, or needs additional scope.

Calibrating and then judging success solely on the same standards can hide defects. Include independent 25/75/100 Ω loads or another characterized network.

## 10. Boundary validation and resource limits

Every value below marked P is a proposed host boundary, not a device specification.

| Boundary | Known evidence | Required policy |
|---|---|---|
| Outgoing USB command | 64-byte API buffer / two-byte wrapper | Maximum 62 payload bytes in this source layout; refuse overflow; qualify descriptor |
| Incoming USB frame | Source reads 64 bytes | Verify actual length before header/payload access; wrong ID/oversized declared length cannot produce measurements |
| Pending text | Header names 32768 but append path is unbounded | P: enforce 32768-byte pending cap initially; process/drain incrementally; fail operation on overflow |
| Complete line | No firmware max established | P: 4096-byte cap initially, with typed bounds for measurement/identity; revisit from captures |
| Measurement tokens | Comma-separated groups of three | Strict complete triplets, C-locale decimal parsing, finite values; no partial numeric success |
| Frequency | Stick Pro documented 100000…600000000 Hz | Validate start ≤ stop, entire span, center arithmetic; zero-span only in a qualified mode |
| Grid / quantization | Front-panel 1 kHz entry; BLE truncates to kHz | Preserve requested/effective/device-returned frequencies; learn per-transport rules |
| R/X | Published expected range | Flag out-of-range finite values; no silent clamping; profile determines rejection versus retained flagged raw sample |
| Z0 | Documented choices / host math requires positive | Finite positive value; initial UI uses documented choices, records chosen reference |
| Point count | 2000 is client default; firmware max unknown | P: first experiment FRX100; production menu count only after grid/count proof; reject zero/negative/oversized input |
| ACK sequencing | Untagged OK/ERROR | One operation owner; stage-specific handling; no overlapping sweeps |
| Timeouts | Source polling values, no verified timing maxima | Monotonic deadlines; separate identity, ACK, first sample, inter-sample and total sweep deadlines |
| Reconnect | No wire acquisition ID | Retire generation, clear timers/queues, qualify clean input boundary; no automatic measurement replay |
| History | No device-level host history bound | P: bounded traces; no unbounded repeat capture |
| File imports | JSON / text inputs | Cap file size, records and numeric fields; reject malformed metadata; never execute imported notes |

All timers and caps need documented owners and diagnostics. A parser error should identify stage, operation, received/expected count and bounded relevant bytes. Do not log serial/MAC unnecessarily in public reports.

Source flaws to avoid: unchecked outgoing length; permissive bad numeric delivery; unbounded incoming text; shared static command state; timeout interpreted as completion; host-endian serialization; silent invalid-measurement substitutions.

## 11. Files and reproducibility

[S] AntScope2 can save .asd JSON with DotsNumber and a Measurements array of fq/r/x; the saved array may be the host-corrected one. Its CSV header uses semicolons while rows use commas. It supports .s1p exports with MHz and S RI / S MA variants, as well as a Z RI option.

[P] Do not reproduce inconsistent CSV delimiters or four-significant-digit S-parameter precision merely for compatibility.

Recommended first exports:

- CSV with unambiguous columns `frequency_hz,r_ohm,x_ohm`, consistent delimiter, sufficient precision.
- Touchstone **one-port S RI** with explicit frequency unit and reference impedance. Store dimensionless Γ, not unnormalized ohms in an S row.
- Versioned measurement session file with immutable device R/X, requested and actual range/count, status, calibration provenance, device tuple, UTC capture times, notes, and selected display Z0.

Distinguish live vs saved, complete vs partial, and device vs host-corrected samples. Store reference traces independently of the live session. Use atomic file replacement; a failed save must not corrupt an existing trace.

Round-trip tests must verify units, precision, ordering, quality flags, Z0, and negative reactance. Compare with an independent Touchstone reader. Do not manufacture S21/S12/S22 or emit a two-port dataset for this device.

References: [save/export/import implementation][measurements], [export controls][export].

## 12. Proposed AetherLab integration contract

### 12.1 Session and workspace ownership

[P] Reuse the station's tab affordance, with **AetherLab as an instrument workspace**. The analyzer owns independent identity, connection, acquisition, and data state. It does not need receiver slices, audio channels, a transceiver panadapter, or a fabricated radio backend.

The surveyed [MainWindow_Session.cpp](https://github.com/aethersdr/AetherSDR/blob/ae699be2580cc6c89d6d56790db18ec497d9dc99/src/gui/MainWindow_Session.cpp#L547-L565) has radio-tab activation at line 547: selecting a different radio opens the picker. An AetherLab tab therefore needs its own workspace activation route; existing tabs are not already independent persistent radio sessions.

The above project link pins the surveyed source. Re-check current project source when implementation begins.

[P] Switching to AetherLab preserves the connected radio's state and layout. Switching back restores the radio view. A lab-selected state and a radio-connected state must remain separate. Disconnecting the analyzer preserves its last trace with explicit age/status.

Use a gui-free acquisition/model path in the engine, then render in the workspace. New GUI wiring belongs in a MainWindow sibling TU. Persistence follows AppSettings feature ownership. These are proposals subject to repository review, not implemented seams.

### 12.2 Physical path and RF intent

The analyzer emits a measurement stimulus. It must be physically isolated from a transmitter before an authorized sweep. Software tab selection cannot verify an antenna switch, eliminate DC, or protect against another client/transmitter.

[P] AetherLab's Sweep is an RF-producing action and must participate in the appropriate automation/keying safety contract. Do not assume existing AETHER_AUTOMATION_NO_TX automatically covers a new analyzer action. Observe-only access must remain non-emitting; sweeping in an automated bench test needs explicit permitted intent.

[P] A proposed lab interlock must cover all AetherSDR-originated TX entry points, including external control clients and deferred producers, not just greyed-out MOX/TUNE buttons. It cannot claim protection from independent station software or a physical radio PTT. Scope this interlock with the maintainer rather than adding a global flag casually.

For the first hardware experiment use **no transceiver RF connection to the fixture**. Later prove the connected-radio RX/session workflow separately. No transceiver transmission is required to validate the PoC.

### 12.3 Instrument UI and bridge

[P] Minimal view: requested/effective sweep range, explicit Sweep/Stop, SWR and R/X, one linked marker, device connection and correction provenance, complete/partial status, saved trace, and return-to-radio action.

“Use current band” copies a range from the active AetherSDR regional band plan; it must not retune the transceiver or start a measurement. Unsupported instrument operations carry a reason.

Current widget bridge actions can exercise controls, but a pixels-only screenshot cannot prove sample count, units, or freshness. A concrete gap for implementation is a **read-only instrument snapshot** exposing identity, operation/stage, requested/actual ranges, counts, timestamp, quality and sample data/digest. Design it through the existing documented bridge mechanisms; do not invent a separate automation service.

## 13. Validation matrix and hardware experiments

### 13.1 Evidence ladder

| Layer | Proves | Does not prove |
|---|---|---|
| Source review | Reference behavior, framing, ordering hypotheses | Target firmware acceptance |
| Source-derived vectors/math | Internal consistency of described packing and equations | Wire captures or instrument accuracy |
| Injected-transport CTests | Parser bounds, transactions, refusals, lifecycle, data math | Device convergence or physical stop |
| Sanitizers | Memory/lifetime behavior under stressed client inputs | Vendor firmware correctness |
| Bridge with fixture data | Widget/model presentation and operator workflow | USB/BLE compatibility or measured RF |
| Live analyzer + bridge | Real identity, sweeps, UI/model correspondence | Transceiver integration or every model |
| Passive fixture/reference instrument comparison | Qualified metrology at measured conditions | Accuracy outside tested envelope |
| Connected transceiver RX/session evidence | Tab return, state preservation, receive continuity | TX safety or RF switching |
| Physical RF stop measurement | Stop/output behavior under identified conditions | All fault conditions or external-client protection |

### 13.2 Planned injected tests

All are **planned / not run** against an AetherSDR implementation.

| ID | Contract | Inputs / acceptance |
|---|---|---|
| U-01 | HID packing | Exact command/terminator bytes, zero padding, payload limit, short write handling |
| U-02 | HID decoding | Short/header-only/wrong-ID/oversized-count frames; fragmentation at every boundary; no invalid sample delivery |
| U-03 | Line parsing | Split CR/LF, multiple lines per report, blank lines, malformed triplets, NaN/Inf, locale comma, buffer/line caps |
| U-04 | ACK sequencing | Delayed/duplicate/unsolicited OK, ERROR in each stage; no premature or repeated FRX |
| U-05 | Cancellation | Cancel during identity, center ACK, span ACK, first sample, middle, final sample; retired operation cannot dispatch |
| U-06 | Freshness | Unplug/replug, queued callbacks, stale ACK/data, same/different device; generation fencing and clean boundary |
| U-07 | Count and grids | Target-qualified N convention; missing/duplicate/out-of-order/out-of-range samples; partial never complete |
| U-08 | Math | §8 fixtures, Γ phase distinction, match/open/short, threshold crossings, multiple minima, edge-truncated bandwidth |
| U-09 | Data ownership | Display clipping/correction does not overwrite raw samples; saved trace survives session close |
| U-10 | Files | CSV/S1P round-trip, units/Z0, precision, atomic failure, malformed/oversized input |
| U-11 | RF intent | Tab entry/reconnect/profile restore/Use current band do not sweep; automatic retries cannot replay measurement intent |
| U-12 | Session view | Radio session/tuning/layout preserved across lab selection; analyzer disconnect doesn't disconnect radio |
| U-13 | BLE later | Frame length/CRC/endian; both sample variants; bad IDs, missing groups, packed-value fixtures, bounded queue |
| U-14 | Metrology provenance | Unknown device OSL is visibly unknown; host and device correction states cannot be conflated |

Use socket-free transport injection in default CTests. A made-up live USB/serial/network peer does not qualify RigExpert firmware. Register tests in tests/tests.cmake and follow docs/agents/tests-ci.md; do not grow the frozen PR gate as part of this feature.

Run Qt tests with QT_QPA_PLATFORM=offscreen. Build with exactly cmake --build <build-dir> -j22; run eligible selections with ctest --test-dir <build-dir> -j22 --no-tests=error and the current changes. Repository workflow is authoritative.

### 13.3 Planned hardware qualification

Every row is **pending**. Hardware contact requires an explicit authorized bench session and a check that the device is available.

| ID | Experiment | Required record / decision |
|---|---|---|
| H-01 | Inventory / identity | Model, revision, firmware, complete serial stored privately, OS, HIDAPI version, VID/PID/interface/report descriptor; VER/FULLINFO capture |
| H-02 | Grid/count | FRX100 and several small/ordinary counts; all returned frequencies, endpoints, count, trailers, timing; define UI count mapping |
| H-03 | Calibration / Z0 | Device OSL off/on, host correction off, direct and extension-cable fixtures, power-cycle/reconnect; determine raw-output provenance |
| H-04 | Accuracy baseline | Matched and mismatched independent loads plus known reactive/passive network; compare raw R/X, front-panel values and AntScope2 |
| H-05 | Bounds | In-range low/mid/high frequencies and supported spans/counts; invalid requests refused locally; no automatic out-of-range device probing |
| H-06 | Stop / faults | Stop during setup/acquisition, unplug, app close, natural completion; raw timing + qualified output observation where a RF-stop claim is needed |
| H-07 | Ownership | AntScope2 conflict, two analyzers, device substitution, bootloader enumeration; never control unintended hardware |
| H-08 | Repeatability / performance | Sweep latency distribution, inter-sample gaps, repeated captures, CPU/UI load; choose timeouts and practical point menu |
| H-09 | Real UI / bridge | Sweep controls reach instrument; snapshots equal raw records; markers/export/save match; disconnect shows stale/partial status |
| H-10 | Radio connected RX | Lab entry and return preserve radio state and demonstrated RX; qualified Aether-originated TX refusal tested without RF emission |
| H-11 | Cross-platform USB | macOS/Windows/Linux report semantics, permissions, hotplug, multi-device selection; claim each OS only after evidence |
| H-12 | BLE expansion | Service/characteristic inventory, variant, CRC return, sequence, dropped data, rounding, stop and platform behavior |
| H-13 | Additional model | Repeat qualification on each ZOOM/Stick tuple before adding a support claim |

H-04 protocol agreement and absolute metrology are separate. AntScope2 using the same analyzer is a client reference, not an independent accuracy standard.

### 13.4 Metrology acceptance

Define tolerances **before** the accuracy experiment:

- Raw parser comparisons should reproduce captured decimal values within their represented precision.
- Compare outputs only at common actual frequencies and the same reference plane/Z0/correction setup.
- Establish absolute R/X and reflection uncertainty using characterized fixtures, connector/cable uncertainty, repeatability, and any obtainable manufacturer accuracy data.
- Use absolute |Γ| error near match, where relative return-loss error becomes ill-conditioned.
- Do not use ideal open/short mathematical values as tight real-device accuracy targets.
- Report performance and valid-data fraction with the tested frequency span and count.
- No blanket “accurate to X” claim until the evidence defines its domain.

### 13.5 Evidence bundle for each bench run

~~~text
evidence/<run-id>/
  manifest.json          device tuple, app SHA/dirty state, OS/libs, source pin
  setup.md              fixture path, correction states, Z0, isolation, restoration
  hid-descriptor.*      where applicable
  transport.jsonl       direction, monotonic time, operation/stage, bounded bytes
  parsed.csv            actual frequency/R/X and validity
  bridge.jsonl          widget actions and read-only model snapshots
  reference.*           AntScope2 uncorrected export / independent fixture data
  screenshots/          human-readable UI evidence
  results.md            explicit pass/fail/unknown per contract
~~~

Keep serial/MAC private or consistently redact public copies. Retain evidence of original and restored device settings. Do not include mockup images as measurement evidence.

## 14. Minimum viable offering and exit gates

### 14.1 Recommended sequence

1. **Research complete:** this oracle plus source snapshot; unresolved claims listed.
2. **USB acquisition spike:** identify selected Stick Pro; one finite FRX sweep; raw capture/export; count and units established.
3. **Data correctness:** device-vs-host correction behavior and passive fixture comparisons qualified.
4. **AetherLab workspace PoC:** explicit sweep, SWR/R-X, marker, save; preserve the connected radio view/session.
5. **MVO hardening:** cancellation, hotplug, stale-data marking, bounds, bridge evidence, package and platform evidence.
6. **Later increments:** overlays, Smith chart, stored-device records, repeat/single-frequency, BLE, other models, cable tools.

### 14.2 MVO acceptance gates

| Gate | Required evidence |
|---|---|
| G-01 Protocol | H-01/H-02: correct selected device, report sizes, ACK sequence, units, count, effective grid |
| G-02 Measurements | H-03/H-04: correction provenance and qualified fixture agreement; no silent substitutions |
| G-03 Lifecycle | U-04…U-07 + H-06/H-07: bounded errors, cancellation, stale-input recovery, ownership |
| G-04 Presentation | U-08…U-10 + H-09: marker, save/export and status correspond to actual dataset |
| G-05 Station workflow | U-11/U-12 + H-10: no automatic sweep/keying; preserved radio session; reviewed interlock scope |
| G-06 Delivery | Current-change build/tests/checks; package includes HID support; user docs and bridge verification; explicit OS/model support boundary |

The first MVO can be **macOS + the operator's Stick Pro USB tuple**, if declared that narrowly. Device-wide capabilities and constants belong in its profile; do not scatter model strings through the GUI. Cross-platform builds are useful but do not establish H-11.

Bluetooth, host OSL wizard, firmware flashing, slot erasure, S21, automatic antenna switching, and broad “all RigExpert” support are outside this MVO.

### 14.3 Immediate next bench experiment

Once authorized and the instrument is available:

- Attach the Stick Pro to USB with a passive 50 Ω load and no transceiver connection.
- Record descriptor + identity.
- Run one 14.000–14.350 MHz FRX100 acquisition and save every received record.
- Repeat on an independent mismatched load to exercise nonzero reflection.
- Compare with AntScope2 with host correction disabled.
- Resolve H-02 count/endpoints and baseline H-03 output provenance before adding graphs.

Do not run this automatically merely because the research document exists.

## 15. Reproducibility and update procedure

The source pin, file hashes and links are in [sources/README.md](./rigexpert-source-index.md) and [sources/manifest.json](./rigexpert-reference-bundle.zip).

Manufacturer web/PDF URLs were accessible through the browsing tool, but direct raw downloads returned **HTTP Error 403: Forbidden**. The official sources directory contains explicitly labelled browser text extracts, not original PDF/HTML files. Never call those extracts byte-identical originals.

[source-derived-vectors.json](./source-derived-vectors.json) contains synthetic command examples. The calculations performed for revision 0.1 checked the entire source CRC-8 lookup table against a polynomial implementation, the standard F4 check value, the BLE example, and the mathematical fixture values. They did **not** exercise an analyzer or AetherSDR implementation.

[verify_oracle.py](./rigexpert-reference-bundle.zip) checks archived hashes, source-reference line ranges, synthetic vectors, and numerical fixtures. Its result is documentation consistency evidence only.

To update:

1. Read the current vendor model documentation; record any source conflicts.
2. Select and record a new source commit rather than citing mutable master.
3. Diff adapters, model table, counts, CRC, calibration, and file conversions.
4. Recompute source manifest and oracle-derived vectors; run consistency checks.
5. Requalify affected hardware tuples. Keep earlier H evidence tied to its firmware/source/app versions.
6. Update oracle date/revision and evidence status; never change a pending result to passed from source review alone.

## 16. Questions that require hardware or vendor answers

| Priority | Question | Why it matters |
|---|---|---|
| Blocker | What is the operator's exact Stick Pro revision/firmware and HID descriptor? | Defines the actual protocol target |
| Blocker | Does FRX<N> return N+1 samples, and what are exact endpoint/rounding rules? | Correct count, plots, completion and exports |
| Blocker | Which factory/user correction layers are present in USB R/X? | Prevents misleading calibration claims |
| Blocker | What establishes a clean stop/restart boundary without wire operation IDs? | Prevents mixed/stale sweeps |
| Blocker | What does off mean physically and what happens on close/unplug? | Bounds RF/output claims and cancellation behavior |
| High | What are qualified frequency/span/count limits and sweep timing? | Correct validation and deadline/menu choices |
| High | Can USB query OSL state, Z0, capability bounds or a measurement counter? | Makes metadata device-confirmed |
| High | What accuracy/uncertainty and input/DC limits apply to this revision? | Safe fixture setup and defensible metrology |
| High | Does changing front-panel Z0 change exported R/X or only derived views? | Correct host/device ownership |
| Later | Which BLE response variant does this Stick Pro expose? | Parser and CRC-return choice |
| Later | Are BLE point/index, sentinel, odd-ID and multiplier rules model-specific? | Avoids importing other-model workarounds |
| Later | Which ZOOM models share the qualified USB path on current firmware? | Expands support by evidence |
| Later | Can stored slots be listed/read without triggering acquisition? | Reliable import and observe-only behavior |

---

## Primary reference links

These source links are pinned. Local source copies are under sources/AntScope2/ inside the downloadable bundle.

[product]: https://rigexpert.com/products/antenna-analyzers/stick-pro/
[manual]: https://old.rigexpert.com/products/uhf-analyzers/stick-pro/users-manual/
[datasheet]: https://rigexpert.com/files/product_documentation/Stick-Pro/Stick-Pro-Aantenna-and-Cable-Analyzer_Datasheet.EN.pdf
[license]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/LICENSE.txt
[adapter]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/analyzerpro.cpp#L248-L449
[models]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/analyzerparameters.h#L172-L380
[identity]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/devinfo/redeviceinfo.cpp#L59-L230
[hid-header]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/hid_analyzer.h#L25-L35
[hid]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/hid_analyzer.cpp#L174-L641
[base]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/baseanalyzer.cpp#L16-L141
[serial]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/com_analyzer.cpp#L319-L326
[aa55]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/AA55BTPacket.cpp#L15-L61
[ble-header]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/ble_analyzer.h#L18-L139
[ble]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/analyzer/ble_analyzer.cpp#L445-L859
[crc]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/crc32.cpp#L125-L135
[measurements]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/measurements.cpp#L647-L1265
[calibration]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/calibration.cpp#L25-L122
[export]: https://github.com/rigexpert/AntScope2/blob/901923c3029e661385fdf88dc7b089cc2263f609/export.cpp
