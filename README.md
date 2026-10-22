# [VonDoom: Digital Lock System](https://requiemdoomed.github.io/VonDoom/)

**Swayam Shakya** · Version 2.1.0 

A lightweight local digital lock, a runnable Python notebook, and an interactive web lab that explains the bits, gates and state transitions behind a sequence detector.

![VonDoom insignia](assets/vondoom-emblem.svg)

## Start in just a minute

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

## Two independent models

| Model | Purpose | Behavior |
|---|---|---|
| PIN controller | Demonstrates software authorization | Whole-PIN comparison; salted PBKDF2 verifier; lockout; auto-lock; PIN rotation |
| Sequence circuit | Teaches computer architecture | Public sequence 10 → 6 → 9; two state bits; decoder; D-register equations |

The circuit is a Moore machine: `S0=00`, `S1=01`, `S2=10`, `S3=11`. Wrong inputs reset to S0. Any key in S3 returns to S0. Idle holds state; Reset clears it. It intentionally has no auto-lock timer; that feature belongs to the PIN controller. The public circuit sequence never unlocks the PIN controller.

## Data and Limitations

Runtime data lives in `data/lock.sqlite3`, with an ownership file beside it. The entire `data/` folder is excluded by `.gitignore`. The ownership file may remain after shutdown; the operating system releases its lock when the process closes. Do not delete it while the controller is running. SQLite contains a random 16-byte salt, a PBKDF2-HMAC-SHA256 verifier with 600,000 iterations, failed attempts, a cooldown deadline and up to 200 events. PINs are never intentionally logged or stored as plaintext. Python strings cannot be reliably wiped from process memory.

This is an educational local access controller, not a physical door lock, encrypted file vault or production authentication service. It gates a demonstration HTTP response. The operating-system account, local filesystem and local programs are trusted. Anyone who can edit the code/database can bypass it. Do not expose the development server to a network. Active cooldowns and the 15-second open window use monotonic time, so a live wall-clock adjustment does not bypass them. Restart recovery uses the persisted wall-clock deadline; changing the clock across a restart can still affect recovery.

If you forget your PIN, stop the server and move `data/lock.sqlite3` to a private backup location, then restart and configure a new PIN. This resets the demonstration and its history; it illustrates why filesystem access is outside this lock's security boundary. Never commit the database or a backup.

Copyright (c) 2026 Swayam Shakya. Released under the MIT License; see [LICENSE](LICENSE).
