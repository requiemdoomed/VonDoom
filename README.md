# VonDoom: Digital Lock System

**Swayam Shakya** · Version 2.1.0 · Python · Computer architecture · MIT License

A lightweight local digital lock, a runnable Python notebook, and an interactive web lab that explains the bits, gates and state transitions behind a sequence detector.

![VonDoom insignia](assets/vondoom-emblem.svg)

The interface draws on Doctor Doom’s emerald cloak, steel mask and gold detailing. Its identity combines deep green surfaces, an angular mask insignia and a focused command-console layout.

## Start in one minute

You need **Python 3.10 or newer**. The application uses only the Python standard library. Extract the ZIP before running it. The project folder is named `VonDoom`.

Open a terminal in the `VonDoom` folder:

```bash
python server.py
```

On macOS/Linux, use `python3` if `python` is unavailable. On Windows, `py -3 server.py` also works with the Python launcher.

Open **http://127.0.0.1:8765**. Create a private PIN containing 6–12 digits, confirm it, then unlock. There is no default PIN. Try the protected response while unlocked, then press **Lock now**. Five wrong PINs trigger a 30-second cooldown. Access automatically expires after 15 seconds.

Stop the server with **Ctrl+C**. If the port is occupied:

```bash
python server.py --port 8766
```

Open http://127.0.0.1:8766 instead. The program now rejects a second controller for the same database, even on another port. Close the first one before restarting.

## Use the notebook

The app does not require Jupyter. To use `VonDoom.ipynb`, install JupyterLab in a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install jupyterlab
python -m jupyterlab
```

If PowerShell activation is restricted, use `.venv\Scripts\python.exe -m pip install jupyterlab` and `.venv\Scripts\python.exe -m jupyterlab` directly.

Open the notebook from the project folder. Select a Python kernel and run cells from top to bottom. The notebook covers:

1. Imports and project layout
2. Decoder and gate equations
3. Exhaustive state-transition verification
4. Sequence trace and output LEDs
5. PIN setup, unlock, protected access and relock
6. Deterministic lockout and auto-lock experiments
7. Entropy and complexity calculations
8. Measured gate-evaluation timing
9. Full test suite
10. Optional interactive private-PIN exercise and web-server launch

The demonstrations use disposable temporary databases and a clearly labeled example PIN. They do not change your web console PIN. Set `RUN_PRIVATE_DEMO = True` to enter a PIN with `getpass`; set `RUN_WEB = True` to launch the real web controller from the notebook. Run the final stop cell when finished. Keep the kernel alive while using the notebook-hosted server. Do not run the standalone server on the same port at the same time.

## Open index.html directly

Double-click `index.html` for an offline showcase. The keypad, step-through controls, live timing waveform, gate self-check, truth tables, clock trace, CSV export and saved theme work without Python. Access controls stay disabled until you open the page through the Python server.

A browser cannot execute an `.ipynb` file. The notebook and server import the same Python controller; the web page calls the server over local HTTP.

## Two independent models

| Model | Purpose | Behavior |
|---|---|---|
| PIN controller | Demonstrates software authorization | Whole-PIN comparison; salted PBKDF2 verifier; lockout; auto-lock; PIN rotation |
| Sequence circuit | Teaches computer architecture | Public sequence 10 → 6 → 9; two state bits; decoder; D-register equations |

The circuit is a Moore machine: `S0=00`, `S1=01`, `S2=10`, `S3=11`. Wrong inputs reset to S0. Any key in S3 returns to S0. Idle holds state; Reset clears it. It intentionally has no auto-lock timer; that feature belongs to the PIN controller. The public circuit sequence never unlocks the PIN controller.

## Project map

```text
VonDoom/
  VonDoom.ipynb       Guided runnable notebook
  index.html              Main interactive web page
  server.py               Loopback HTTP server and notebook launch helpers
  verify.py               One-command project verification
  locksystem/
    core.py               Authentication, timers, SQLite and event journal
    logic.py              Decoder, gate equations and reference FSM
    ownership.py          One-controller-per-database guard
  assets/                 Local CSS, JavaScript and editable SVG diagrams
  docs/
    ENGINEERING.md        Derivations, design decisions and threat model
    TESTING.md            Checks, results and verification limits
    truth-table.csv       All 64 state/input combinations
  tests/                  Python behavior and HTTP tests; JavaScript checks
  LICENSE                 MIT License
```

## Verify it yourself

From the project folder:

```bash
python verify.py --notebook
```

This runs the Python tests, checks project assets, executes the notebook, and runs frontend/HTTP integration checks when Node.js is available. Optional notebook flags must be False. To run only the Python suite:

```bash
python -m unittest discover -s tests -v
```

Optional frontend checks, if Node.js is installed:

```bash
node --check assets/app.js
node tests/test_frontend.cjs --integration
```

Python tests include a real default-cost PIN hash and local HTTP requests. Most behavioral tests use a faster hash and simulated clocks so they finish quickly. No test waits 30 real seconds.

## Data and limits

Runtime data lives in `data/lock.sqlite3`, with an ownership file beside it. The entire `data/` folder is excluded by `.gitignore`. The ownership file may remain after shutdown; the operating system releases its lock when the process closes. Do not delete it while the controller is running. SQLite contains a random 16-byte salt, a PBKDF2-HMAC-SHA256 verifier with 600,000 iterations, failed attempts, a cooldown deadline and up to 200 events. PINs are never intentionally logged or stored as plaintext. Python strings cannot be reliably wiped from process memory.

This is an educational local access controller, not a physical door lock, encrypted file vault or production authentication service. It gates a demonstration HTTP response. The operating-system account, local filesystem and local programs are trusted. Anyone who can edit the code/database can bypass it. Do not expose the development server to a network. Active cooldowns and the 15-second open window use monotonic time, so a live wall-clock adjustment does not bypass them. Restart recovery uses the persisted wall-clock deadline; changing the clock across a restart can still affect recovery.

If you forget your PIN, stop the server and move `data/lock.sqlite3` to a private backup location, then restart and configure a new PIN. This resets the demonstration and its history; it illustrates why filesystem access is outside this lock's security boundary. Never commit the database or a backup.

## Put it on GitHub

Upload the extracted project files to a new repository, including `.gitignore`. Do not upload the ZIP inside the repository or include `.venv`, `data`, notebook checkpoints, private outputs or temporary files. Review notebook outputs after entering personal data.

GitHub Pages can host the static showcase, but cannot run the Python controller. Live lock controls require the local server. No API key, paid service, model download or external image/font request is needed.

## Visual identity in version 2.1

The application, notebook, diagrams and documentation now use **VonDoom: Digital Lock System**. The emerald, steel and gold interface includes a matching local SVG insignia and favicon, with coordinated dark and light themes. Swayam Shakya remains the project author.

## What changed in version 2

- One controller owns each database; duplicate launches fail with a clear message.
- Active cooldowns resist wall-clock jumps, and malformed stored credentials fail closed.
- The server limits concurrent workers and rejects ambiguous headers, duplicate JSON fields and unexpected request fields.
- The logic lab adds a timing waveform, a step button and a fresh 64-case self-check.
- PIN changes require confirmation. Stale polling responses cannot overwrite a newer action.
- `verify.py` checks the whole project; tests exercise the JavaScript against the real Python server.

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for details.

## License

Copyright (c) 2026 Swayam Shakya. Released under the MIT License; see [LICENSE](LICENSE).
