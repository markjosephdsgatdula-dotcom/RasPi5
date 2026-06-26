# Implementation Plan: UR10e XML-RPC Integration on Raspberry Pi 5

Integrate a lightweight XML-RPC server running on the Raspberry Pi 5 on Port 8000. This provides a robust, network-based alternative to the physical GPIO triggers, bypassing any hardware optocoupler isolation issues. The UR10e robot arm will trigger image captures and cycle resets directly over the local network via URScript XML-RPC calls.

## Status

| Item | Status |
|---|---|
| `main.py` — XML-RPC server added | ✅ Done (commit `0a84dc0`) |
| `main.py` — `session_lock` thread safety | ✅ Done (commit `0a84dc0`) |
| `test_xmlrpc_client.py` — test script | ✅ Done |
| Local simulation test (PC) | ⬜ Pending |
| Live test on Pi 5 | ⬜ Pending (Pi currently off) |
| UR10e URScript integration | ⬜ Pending |

---

## Network Configuration

> [!IMPORTANT]
> **Pi IP Address:** `192.168.1.112` (confirm with `ip addr` on the Pi — may have changed from `192.168.1.189`)
>
> **Port:** XML-RPC server binds to `0.0.0.0:8000`. Ensure no other service uses port 8000 and that the Pi's firewall allows TCP on port 8000.
>
> **URScript initialization:**
> ```
> camera = xmlrpc("http://192.168.1.112:8000")
> ```

---

## What Was Implemented

### `main.py` changes (commit `0a84dc0`)

- **Import:** `from xmlrpc.server import SimpleXMLRPCServer`
- **`session_lock`:** `threading.Lock()` added at module level — guards all `session` dict writes in `on_robot_trigger()` and `on_product_done()` against concurrent GPIO + XML-RPC calls
- **`RobotXMLRPCInterface` class** inside `main()` with 4 methods:
  - `capture_weld()` / `trigger_capture()` → calls `on_robot_trigger()`
  - `cycle_complete()` / `product_done()` → calls `on_product_done()`
- **Server thread:** `SimpleXMLRPCServer` on `("0.0.0.0", 8000)` runs as a daemon thread
- **Graceful shutdown:** `rpc_server` initialized to `None`; guarded with `if rpc_server:` in `finally` block before calling `shutdown()` and `server_close()`

### `test_xmlrpc_client.py` (new file)

A lightweight test script that simulates UR10e XML-RPC calls. Takes an optional IP argument (defaults to `localhost`).

---

## URScript Code (UR10e Side)

Add the following to your PolyScope robot program:

```urscript
# Run once in the Installation tab or program header
camera = xmlrpc("http://192.168.1.112:8000")

# Inside the weld movement loop — robot pauses here until Pi returns True
success = camera.trigger_capture()

# At the end of each product cycle
camera.product_done()
```

---

## Verification Plan

### Step 1 — Local simulation test (no Pi needed)

Run on this Windows PC to confirm the XML-RPC server starts and responds:

```bash
# Terminal 1
python main.py

# Terminal 2 — after the UI opens
python test_xmlrpc_client.py
```

Expected output in Terminal 2:
```
Connecting to XML-RPC server at: http://localhost:8000
[TEST 1] Calling 'trigger_capture' / 'capture_weld'...
Server response (success status): False   ← False because no session is active yet, which is correct
[TEST 2] Calling 'product_done' / 'cycle_complete'...
Server response (success status): True
Verification checks complete!
```

### Step 2 — Live test on Pi 5

```bash
# On the Pi — pull latest and run
git pull
python main.py

# From this PC — point test client at the Pi
python test_xmlrpc_client.py 192.168.1.112
```

Verify in the UI:
1. Startup log shows `[INIT] XML-RPC server listening on port 8000`
2. Test client calls appear in the UI console as `[XML-RPC] Received ...`
3. Start a session, then re-run the test client — `trigger_capture` should now return `True` and save an image
4. Close the app and relaunch — confirm no `Address already in use` error

### Step 3 — UR10e end-to-end test

1. Load the URScript above into PolyScope
2. Confirm the robot pauses at `trigger_capture()` and resumes after the Pi saves the image
3. Confirm `product_done()` resets the weld index in the UI

---

## SSH Access (for deployment)

- **Host:** `192.168.1.112`
- **User:** `rinkamarkmaaku`
- Note: Password auth may be disabled on the Pi — verify `PasswordAuthentication` in `/etc/ssh/sshd_config`
