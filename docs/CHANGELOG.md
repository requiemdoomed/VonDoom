# Changelog

## 2.1.0 — 2026-10-22

- Rename the project to VonDoom: Digital Lock System throughout the page, notebook, server and documentation.
- Introduce a Doctor Doom-inspired emerald, steel and gold visual identity, with an editable SVG mask-and-hood insignia.
- Redesign the hero, navigation, console panels, buttons and theme styling.
- Coordinate architecture diagrams and demo illustrations with the new palette.
- Preserve the Python controller and its tested behavior.


## 2.0.0 — 2026-10-22

### Controller fixes

- Prevent two controllers from opening the same database, including controllers on different ports. A second owner now receives a readable error instead of running a separate access window.
- Track active cooldowns with monotonic time. A live wall-clock jump no longer skips or prolongs a cooldown.
- Restore cooldowns from the saved deadline at startup, with a maximum restored duration of 30 seconds. Clock changes across restarts remain a documented limitation.
- Validate the stored credential record before serving requests. Invalid salt, verifier, iteration count or failure state prevents startup.
- Release ownership after failed startup and make close() safe to call twice. Add context-manager support for notebook experiments.

### HTTP fixes

- Cap concurrent request workers at eight and return 503 when full.
- Reject duplicate or missing required headers, transfer encoding, repeated JSON keys, incomplete bodies and unexpected fields.
- Validate the port before opening a database.
- Revoke the in-memory access window when a storage operation fails.
- Handle disconnected clients and socket timeouts without printing credential-bearing request data.

### Interface improvements

- Add a discrete timing waveform for clock, both state bits and the green output.
- Add step-through controls and a live exhaustive 64-transition self-check.
- Require confirmation when replacing a PIN.
- Remember the selected theme when local storage is available.
- Ignore stale status polls after a newer user action.
- Clear protected response text on connection failure and refresh expired process tokens without automatically replaying an action.
- Expand HTML and CSS into readable, editable files.

### Verification and documentation

- Extend the tests for database ownership, clock changes, malformed requests and worker saturation.
- Exercise the actual frontend request functions against a real Python server, including stale polling and disconnected-state behavior.
- Add verify.py for source, asset, test, integration and optional notebook checks.
- Add notebook experiments for clock changes and exclusive database ownership.
- Update the README and engineering notes to describe behavior and limits precisely.

## 1.0.0 — 2026-10-22

Initial local PIN controller, notebook, sequence circuit, web showcase and tests.
