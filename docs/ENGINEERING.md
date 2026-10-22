# Engineering notes

Author: Swayam Shakya

## 1. Architecture and responsibility

The local browser handles presentation. A standard-library HTTP server accepts a small allowlist of static files and JSON endpoints. The Python `DigitalLock` owns authentication, state and deadlines. SQLite stores the verifier and persistent cooldown state. An RLock serializes operations from request threads; the database connection is not shared without that mutex. An operating-system lock on a sidecar ownership file prevents a second controller from opening the same database. Unix uses flock; Windows uses a one-byte file lock. Closing or terminating the owner releases the OS lock. The sidecar file is intentionally retained, since deleting it while an owner runs could break ownership coordination.

The notebook imports exactly the same controller. It is an executable explanation and alternative launch point, not a separate copy of the access-control algorithm.

## 2. Sequence detector

Let Q1 Q0 encode the state and B3 B2 B1 B0 encode the submitted key. Every press represents one synchronous clock edge. Inputs are unsigned values 0–15.

| State | Bits | Meaning | Green |
|---|---|---|---|
| S0 | 00 | Locked, no prefix matched | 0 |
| S1 | 01 | Key 10 matched | 0 |
| S2 | 10 | Keys 10, 6 matched | 0 |
| S3 | 11 | Keys 10, 6, 9 matched | 1 |

All unspecified transitions go to S0. This machine does not reuse the wrong key as the start of a new prefix. Thus 10,10,6,9 does not unlock. S3 clears on any submitted key. Reset clears state independently; idle holds state.

Using `~` for NOT, `&` for AND and `|` for OR:

```text
I10 = B3 & ~B2 & B1 & ~B0
I6  = ~B3 & B2 & B1 & ~B0
I9  = B3 & ~B2 & ~B1 & B0

T0 = ~Q1 & ~Q0 & I10
T1 = ~Q1 & Q0 & I6
T2 = Q1 & ~Q0 & I9

D1 = T1 | T2
D0 = T0 | T2
Green = Q1 & Q0
Red = ~Green
```

Python's bitwise complement is not a single-bit NOT. The implementation uses `1-bit` for inversion of normalized 0/1 values. `next_state = (D1 << 1) | D0` packs the sampled bits.

These equations follow directly from the only transitions with high output bits: 00→01 on 10, 01→10 on 6, and 10→11 on 9. There are no other high next-state bits.

## 3. Karnaugh-map projection

The decoder categories below are one-hot signals, not an independent binary axis. This is a projection of the full six-variable map, not a conventional two-variable K-map. State rows use Gray order. The complete binary truth table is `truth-table.csv`.

| Q1 Q0 | D1 for I10 | D1 for I6 | D1 for I9 | D1 for other |
|---|---|---|---|---|
| 00 | 0 | 0 | 0 | 0 |
| 01 | 0 | 1 | 0 | 0 |
| 11 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 1 | 0 |

| Q1 Q0 | D0 for I10 | D0 for I6 | D0 for I9 | D0 for other |
|---|---|---|---|---|
| 00 | 1 | 0 | 0 | 0 |
| 01 | 0 | 0 | 0 | 0 |
| 11 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 1 | 0 |

For a conventional six-variable map, partition by Q1 Q0 in Gray order and plot B3 B2 against B1 B0, both in Gray order 00,01,11,10. D1 has minterms 22 and 41; D0 has minterms 10 and 41, when Q1 is the most significant of six bits. They are isolated cells, so the direct sum-of-products has no adjacent groups. Factoring the shared input minterms into the decoder gives the equations above.

## 4. Datapath and control

The input bus is four bits; the state register is two bits. Combinational decoding produces I10/I6/I9. State qualification produces T0/T1/T2. Two OR gates produce D1/D0. Two D flip-flops sample the results together. Q feeds both the next-state logic and the output decoder.

The software variable assignment models the clock edge. It does not model electrical hazards, metastability, fan-out or propagation delay. A hardware implementation would need input synchronization/debounce, a clock/reset design, voltage compatibility and an actuator driver with an independently safe failure state. A 4×4 physical keypad would also require scanning and encoding, which this software does not pretend to implement.

## 5. PIN controller state machine

| Current state | Event | Next state / effect |
|---|---|---|
| UNCONFIGURED | Valid setup | LOCKED; persist verifier |
| LOCKED | Correct PIN | UNLOCKED for 15 seconds; clear failures |
| LOCKED/UNLOCKED | Wrong PIN | LOCKED; increment failures |
| Any configured state | Fifth wrong PIN | LOCKOUT for 30 seconds |
| LOCKOUT | Any PIN | Denied; no hash work or reset |
| LOCKOUT | Cooldown expires | LOCKED; reset failures |
| UNLOCKED | Deadline or manual lock | LOCKED |
| Configured, not locked out | Correct current PIN + valid replacement | LOCKED with new salt/verifier |
| Any state | Process restart | No active open window; stored cooldown remains |

The controller validates stored credential fields before accepting requests and evaluates deadlines before every status or authorization operation. It needs no timer thread to enforce access expiry. The event documenting auto-lock appears at the first operation after expiry. UI polling updates the display roughly once a second; the polling interval does not extend access.

An incorrect PIN while unlocked revokes access. A malformed PIN is rejected as invalid input and does not consume a guess, since it is not part of the accepted PIN space. Changing a PIN uses the same failure counter as unlocking. Manual locking never clears a cooldown.

## 6. Authentication and storage

PBKDF2-HMAC-SHA256 uses 600,000 iterations, a fresh random 16-byte salt and a 32-byte verifier. The cost is stored alongside each verifier. `hmac.compare_digest` compares derived bytes. This is a password-derivation demonstration, not a claim of sufficient security for every deployment.

The event log excludes PINs, salts and verifiers. It retains 200 entries; the UI receives the most recent 20. No remote telemetry or external asset service is used. SQLite transactions protect individual persistence updates; process crashes during an operation can leave the last committed step in place. Restart never restores an unlocked session.

## 7. Mathematics

- State storage: ceil(log2(4)) = 2 bits.
- Decoder space: 2^4 = 16 input values.
- Exhaustive transition checks: 4 × 16 = 64.
- Three independent uniformly chosen keys: 16^3 = 4096 combinations, log2(4096) = 12 bits. The published sequence itself is not secret.
- A uniform six-digit PIN: 10^6 values, log2(10^6) ≈ 19.93 bits. Leading zeroes are valid.
- Sustained online guess rate: at most roughly 5/30 guesses per second, ignoring computation time. Expected guesses for a uniform secret without repetition are approximately half the space. This yields roughly 50,000 minutes for six digits under the simplified model. This is not an offline cracking estimate or a guarantee.
- Gate computation: O(1) time and space per edge. Hash verification: O(c) work for fixed-length input and iteration count c. Stored event count is bounded.

## 8. HTTP interface

| Method | Route | Role |
|---|---|---|
| GET | /api/session | Bootstrap process token and status |
| GET | /api/status | Public local state and recent event labels |
| POST | /api/setup | First-run PIN creation |
| POST | /api/unlock | Whole-PIN verification |
| POST | /api/lock | Revoke access |
| POST | /api/change-pin | Verify current PIN, replace verifier, relock |
| POST | /api/protected | Return demo content only when unlocked |

POST requests require JSON, a matching loopback Host and Origin, and the bootstrap token in `X-Lock-Token`. The body is limited to 1024 bytes. Required headers must appear exactly once; transfer encoding, duplicate JSON keys and unexpected fields are rejected. At most eight request workers run concurrently; excess clients receive HTTP 503. Each connection has a five-second socket timeout. This bounds worker count, not total CPU consumption or all denial-of-service risks. Static paths are allowlisted, preventing accidental exposure of the notebook, database or Python sources. There are no CORS grants. Responses use no-store, nosniff and a restrictive content security policy.

The token is a browser cross-origin defense, not user authentication. Any trusted local client can fetch it. This is a single-controller local lab; tabs share one lock state. There are no users, roles, distributed sessions, encrypted storage or TLS. The built-in HTTP server is for local demonstration only.

## 9. Filesystem and clock threat boundary

A copied verifier can be attacked offline. A modified database or program can bypass the demonstration. Initial PIN setup is available to the first local client, so run it in a trusted local session. Filesystem permissions and endpoint security are outside the application.

Open-window expiry and active cooldown both use monotonic time. When the controller opens its database, it converts the persisted wall-clock deadline to a remaining cooldown, capped at 30 seconds, then tracks it with monotonic time. Wall-clock changes cannot skip a live cooldown. Clock changes while the process is stopped can still change the restored duration. A production design would need a trusted external rate-limit/state boundary and a real threat model.

## 10. Frontend consistency

An action increments a local request generation. A status poll started before that action is discarded if it returns late. A new process token is fetched after a rejected stale token; the failed mutation is never retried automatically, avoiding duplicate submissions. Fetches time out after seven seconds, and sensitive response text is cleared on disconnection or request failure. The waveform displays discrete event steps, not physical propagation delay or elapsed time.
