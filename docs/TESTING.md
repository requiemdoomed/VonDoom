# VonDoom validation record

Validated on 2026-10-22 using Python 3.12.14 and Node.js 24.19.0 on Linux x86_64.

## Completed checks

- 54 Python unittest cases passed.
- Python gate equations matched the independent transition model for all 64 state/input pairs.
- Every row of the supplied 64-row truth-table CSV matched the implementation.
- JavaScript gate equations passed the same 64 expected transitions.
- The DOM harness checked keypad construction, accepted sequence, reset, 32-row trace retention, setup controls, lockout controls, unlocked access and offline disabling.
- All 14 notebook code cells executed in order in a clean Python namespace. Demonstration outputs are included. Optional private prompts and the persistent web-server cell were left off, as documented.
- HTTP tests exercised a real local server, bootstrap token, setup, unlock, protected access, manual lock, invalid requests, origin/token rejection and restricted static-file serving.
- Controller tests exercised exact timer boundaries, restart relocking, persistent cooldowns, PIN rotation, concurrent failed guesses, unique salts and bounded journal retention.
- One test used the default 600,000-iteration KDF. Other behavior tests used a reduced KDF cost to keep the suite fast.
- Python source compilation and JavaScript syntax checks passed.
- Ownership tests covered duplicate controllers in the same process and a second Python process, startup failure cleanup and credential validation.
- Clock tests covered live wall-clock jumps, partial cooldown recovery and restart after expiry.
- Protocol tests covered duplicate headers, duplicate JSON fields, truncated bodies and excess concurrent connections.
- Frontend integration covered token refresh, stale status replies and disconnected-state behavior.
- The verifier has regression tests to distinguish actual notebook flag assignments from instructions printed as text.

## What these checks do not establish

The notebook cells were executed directly from their source; an installed JupyterLab GUI/kernel integration was not available for validation. The notebook follows nbformat 4.5 and contains standard Python cells.

A cloud-browser preview attempt was blocked by the environment's URL policy. Browser-rendered layout, mobile rendering, focus behavior, theme contrast and the live browser-to-Python interaction were not visually verified. Frontend event behavior was checked with a small DOM harness; HTTP behavior was also checked through the actual JavaScript request/action functions against a real Python server. This is not a substitute for a real browser acceptance test.

Windows and macOS were not available for execution. The code uses standard-library cross-platform paths, SQLite, threading and HTTP APIs, and README commands cover both systems. Run the test suite on your own machine before relying on it.

No physical hardware, production server load test, penetration test or independent security audit was performed. Passing tests does not prove the absence of all bugs.

## Quick manual acceptance test

1. Start `python server.py`; open the printed local URL.
2. Create a new 6–12 digit PIN, then unlock. Check the green state and protected response.
3. Wait at least 15 seconds; protected access should be denied again.
4. Enter five wrong valid-format PINs. Check the 30-second lockout, including after a server restart.
5. Wait for cooldown; unlock with the correct PIN.
6. Change the PIN using the current PIN. Confirm the old PIN fails and the new one works.
7. In the independent logic lab, press 10, 6, 9; check 01, 10, 11 and Green=1. Press any key; check 00.
8. Export a CSV trace, toggle the theme and inspect the page at narrow and wide window sizes.
9. Stop the server, open index.html directly and confirm only the offline lab is active.

## Repeat the automated checks

```bash
python -m unittest discover -s tests -v
node --check assets/app.js
node tests/test_frontend.cjs --integration
```

Node.js is optional and needed only for the JavaScript checks. Neither Node.js nor Jupyter is required for the normal Python web app.

To run all available checks, including the notebook, use `python verify.py --notebook`. See CHANGELOG.md for the version 2 fixes.

## Version 2.1 identity check

The renamed project passed the same Python, JavaScript integration and notebook checks. The new SVG insignia was rendered to PNG and visually inspected. The complete browser layout remains subject to the browser-testing limitation above.
