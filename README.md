# GetMotion Python SDK

Official Python SDK for the GetMotion API.

## Requirements

- Python 3.9+
- A GetMotion API key

## Installation

Install from source in this repository:

```bash
pip install -e .
```

Or install build/runtime dependencies directly:

```bash
pip install httpx
```

## Quick Start

```python
from getmotion import GetMotion, JobFailedError, WaitTimeout

with GetMotion(api_key="gm-...") as client:
    job = client.jobs.create(title="my-video")
    job.upload_audio("/path/to/audio.mp3")
    job.start()

    try:
        job.wait_for("AWAITING_REVIEW", timeout=600, poll_interval=5)
        proposal = job.get_proposal()
        job.submit_review(proposal)

        session = job.init_storyboard()
        session.chat("Make transitions snappier.")
        session.finalize()

        job.render()
        job.wait_for("COMPLETED", timeout=1800, poll_interval=10)
        renders = job.get_renders()
        print(renders)
    except JobFailedError as exc:
        print(f"Job failed: {exc} (code={exc.code})")
    except WaitTimeout as exc:
        print(f"Timed out waiting for {exc.target_status}")
```

## Render Progress (Percentage Updates)

`job.wait_for(...)` is useful for blocking until a target status, but if you want live render progress you should poll `job.status()` and print progress fields.

```python
import time

job.render()

while True:
    status = job.status()

    current_status = status.get("status")
    stage = status.get("stage")
    detail = status.get("step_detail")
    # Different backend builds may use different progress keys.
    progress = (
        status.get("render_progress_pct")
        or status.get("progress_pct")
        or status.get("progress")
    )

    print(
        f"status={current_status} stage={stage} progress={progress} detail={detail}"
    )

    if current_status in {"COMPLETED", "DONE"}:
        break
    if current_status in {"FAILED", "CANCELLED"}:
        raise RuntimeError(f"Render stopped with status={current_status}")

    time.sleep(10)

renders = job.get_renders()
print(renders)
```

## Main API

### Client

- `GetMotion(api_key, base_url="https://api.getmotion.io", timeout=60.0, debug=False)`
- `client.jobs`: access job APIs
- `client.close()` or use `with GetMotion(...) as client`

### Jobs Resource

- `client.jobs.create(title=None, idempotency_key=None, want_upload_url=False)`
- `client.jobs.get(job_id)`

### Job Methods

- `job.status()`
- `job.wait_for(status, timeout=300, poll_interval=3)`
- `job.upload_audio(path, content_type=None)`
- `job.start(input_s3_key=None)`
- `job.get_proposal()`
- `job.submit_review(decisions, review_token=None)`
- `job.init_storyboard(style="default", force=False, timeout=600, poll_interval=3)`
- `job.render(force=False, keep_bin=False)`
- `job.get_renders(version=None)`
- `job.list_render_versions()`

### Storyboard Session

- `session.get()`
- `session.chat(message)`
- `session.finalize()`
- `session.regenerate(style="default", timeout=600, poll_interval=3)`

## Exceptions

Catch these from `getmotion`:

- `GetMotionError` (base class)
- `AuthenticationError` (401)
- `NotFoundError` (404)
- `ConflictError` (409)
- `JobFailedError`
- `WaitTimeout`

## Logging

Enable debug logging from the SDK:

```python
client = GetMotion(api_key="gm-...", debug=True)
```

Or configure the logger manually:

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("getmotion").setLevel(logging.DEBUG)
```

## End-to-End Example

Run the included script:

```bash
python example.py
```

If you're running against a local API, set `base_url` accordingly (for example `http://localhost:8000`).
