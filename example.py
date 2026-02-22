"""
End-to-end SDK example using an existing S3 audio file.

Run from the getmotion-python directory:
    .venv/bin/python example.py
"""
import time
import logging

import getmotion
from getmotion import GetMotion, JobFailedError, WaitTimeout

# ── logging ──────────────────────────────────────────────────────────────────
# The SDK emits logs under the "getmotion" logger.
# We configure a basic handler here so they print to stdout.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
# Uncomment to see every HTTP request/response:
# logging.getLogger("getmotion").setLevel(logging.DEBUG)

print(f"\ngetmotion SDK v{getmotion.__version__}")
print("=" * 60)

# ── client ───────────────────────────────────────────────────────────────────
# API key auth is disabled locally, any non-empty string works.
client = GetMotion(
    api_key="dev",
    base_url="http://localhost:8000",
)

# ── step 1 · create job ──────────────────────────────────────────────────────
job_title = f"sdk-test-{int(time.time())}"
print(f"\n[1/6] Creating job: {job_title!r}")

job = client.jobs.create(title=job_title)
print(f"      → job.id = {job.id!r}")

# ── step 2 · upload audio + start ────────────────────────────────────────────
AUDIO_PATH = "/tmp/6-brand-audio.mp3"

print(f"\n[2/6] Uploading audio: {AUDIO_PATH}")
job.upload_audio(AUDIO_PATH)
print("      → uploaded")

print("      Starting job (compose_pre)…")
result = job.start()
print(f"      → {result}")

# ── step 3 · wait for review ──────────────────────────────────────────────────
print("\n[3/6] Waiting for AWAITING_REVIEW (compose_pre runs here, ~2 min)…")
try:
    status = job.wait_for("AWAITING_REVIEW", timeout=600, poll_interval=5)
    print(f"      → status={status['status']!r}  stage={status['stage']!r}")
except JobFailedError as e:
    print(f"      ✗ Job failed: {e}  code={e.code}  detail={e.detail}")
    raise SystemExit(1)
except WaitTimeout as e:
    print(f"      ✗ Timed out waiting for {e.target_status!r}")
    raise SystemExit(1)

# ── step 4 · review ───────────────────────────────────────────────────────────
print("\n[4/6] Fetching proposal and submitting review…")
proposal = job.get_proposal()
print(f"      → proposal keys: {list(proposal.keys())}")

# Submit the proposal back as-is (no edits)
job.submit_review(proposal)
print("      → review submitted")

# ── step 5 · storyboard ───────────────────────────────────────────────────────
print("\n[5/6] Initialising storyboard…")
session = job.init_storyboard()
print(f"      → session_id={session.session_id!r}  version={session.version}")

segments = session.high_level_summary.get("segments", [])
print(f"      → {len(segments)} segments")

print("      Sending a chat instruction…")
reply = session.chat("Make the transitions more dynamic and energetic.")
print(f"      → assistant: {reply!r}")

print("      Finalising storyboard (triggers compose_post)…")
session.finalize()
print("      → storyboard finalised, blueprint generated")

# ── step 6 · status check ─────────────────────────────────────────────────────
print("\n[6/6] Checking final job status…")
current = job.status()
print(f"      → status={current['status']!r}  stage={current['stage']!r}")
if current.get("current_blueprint_key"):
    print(f"      → blueprint: {current['current_blueprint_key']}")

print("\n" + "=" * 60)
print("Done. To render, call:")
print(f"  job.render()  # job.id = {job.id!r}")
print("  job.wait_for('COMPLETED', timeout=1800)")
print("  renders = job.get_renders()")
print()

# Uncomment to actually trigger rendering (GPU job, takes several minutes):
# print("\nRendering…")
# job.render()
# job.wait_for("COMPLETED", timeout=1800, poll_interval=10)
# renders = job.get_renders()
# print("Renders:")
# for r in renders.get("renders", []):
#     print(f"  {r['url']}")
