"""
Generates the 6-minute Technical Demo video recording.
Demonstrates:
1. Overview Dashboard & Metrics (1,096 qualified creators, 100% 7-market geo compliance).
2. Agent 1 Normal Run: Discovery & Lead Evidence Passport inspection (all 5 criteria).
3. Agent 2 Lead Scoring & 3-Channel Outreach Studio (Priority A sequences).
4. Refresh on New Input: Idempotency, deduplication & API cost tracking.
5. Recovery from a Simple Failure: Seed Test Lab allowlist enforcement & transport retry backoff.
6. Audit & Export: 20-lead Random Audit Simulator & Final Submission Center export.
"""
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parents[1]
RECORD_DIR = ROOT_DIR / "submission" / "demos" / "video_records"
RECORD_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG_EXE = (
    ROOT_DIR / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe"
)


def record_technical_demo():
    print("[1/3] Launching browser to record 6-minute Technical Demo...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(RECORD_DIR),
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Step 1: 0:00 - 1:00 Executive Dashboard & Architecture
        print("  -> Section 1: Dashboard & Metrics (60s)...")
        page.goto("http://127.0.0.1:8000/#/overview")
        page.wait_for_timeout(4000)

        # Highlight metric cards
        page.evaluate("window.scrollTo({ top: 300, behavior: 'smooth' })")
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo({ top: 700, behavior: 'smooth' })")
        page.wait_for_timeout(6000)
        page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        page.wait_for_timeout(4000)

        # Step 2: 1:00 - 2:15 Part 1: Normal Run (Discovery & Lead Evidence Passport)
        print("  -> Section 2: Normal Run & Evidence Passport (75s)...")
        page.locator(".nav-item", has_text="Creator Discovery").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(5000)

        # Open Creator Database and open Lead Evidence Passport modal
        page.locator(".nav-item", has_text="Creator Database").click()
        page.wait_for_timeout(4000)

        passport_btn = page.locator("button.passport-btn").first
        if passport_btn.count():
            passport_btn.click()
            page.wait_for_timeout(3000)

            # Scroll inside the passport modal drawer to show all 5 verification claims
            modal_body = page.locator("#modal-body")
            if modal_body.count():
                for sy in (250, 500, 800, 1100, 1400):
                    modal_body.evaluate(f"(el) => el.scrollTo({{ top: {sy}, behavior: 'smooth' }})")
                    page.wait_for_timeout(2500)
                modal_body.evaluate("(el) => el.scrollTo({ top: 0, behavior: 'smooth' })")
                page.wait_for_timeout(2500)

            # Close modal
            close_btn = page.locator("#modal-close-btn")
            if close_btn.count():
                close_btn.click()
                page.wait_for_timeout(2000)

        # Step 3: 2:15 - 3:30 Part 2: Scoring & Outreach Studio
        print("  -> Section 3: Scoring & 3-Channel Outreach (75s)...")
        page.locator(".nav-item", has_text="Lead Intelligence").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 300, behavior: 'smooth' })")
        page.wait_for_timeout(4000)

        page.locator(".nav-item", has_text="Outreach Studio").click()
        page.wait_for_timeout(4000)

        # Scroll to inspect email step 1, 2, 3
        page.evaluate("window.scrollTo({ top: 400, behavior: 'smooth' })")
        page.wait_for_timeout(5000)

        # Click LinkedIn tab
        li_btn = page.locator("button, .tab-btn", has_text="LinkedIn").first
        if li_btn.count():
            li_btn.click()
            page.wait_for_timeout(4000)
            page.evaluate("window.scrollTo({ top: 500, behavior: 'smooth' })")
            page.wait_for_timeout(4000)

        # Click Instagram tab
        ig_btn = page.locator("button, .tab-btn", has_text="Instagram").first
        if ig_btn.count():
            ig_btn.click()
            page.wait_for_timeout(4000)
            page.evaluate("window.scrollTo({ top: 500, behavior: 'smooth' })")
            page.wait_for_timeout(4000)

        # Step 4: 3:30 - 4:45 Part 3: Refresh on New Input
        print("  -> Section 4: Refresh on New Input & Cost Tracking (75s)...")
        page.locator(".nav-item", has_text="Agent Control Centre").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 400, behavior: 'smooth' })")
        page.wait_for_timeout(6000)

        # Switch to Discovery history
        page.locator(".nav-item", has_text="Creator Discovery").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 450, behavior: 'smooth' })")
        page.wait_for_timeout(7000)

        # Step 5: 4:45 - 5:30 Part 4: Recovery from Failure (Seed Test Allowlist & Retry)
        print("  -> Section 5: Failure Recovery & Seed Test Lab (45s)...")
        page.locator(".nav-item", has_text="Seed Test Lab").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo({ top: 750, behavior: 'smooth' })")
        page.wait_for_timeout(6000)

        # Step 6: 5:30 - 6:00 Part 5: Quality Audit & Submission Centre Export
        print("  -> Section 6: Audit Simulator & Submission Package (30s)...")
        page.locator(".nav-item", has_text="Quality Audit").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 300, behavior: 'smooth' })")
        page.wait_for_timeout(5000)

        page.locator(".nav-item", has_text="Submission Centre").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(5000)

        context.close()
        raw_video = page.video.path()
        browser.close()

    print(f"[2/3] Playwright recorded raw video: {raw_video}")

    # Convert webm to final standard mp4
    final_mp4 = ROOT_DIR / "submission" / "demos" / "technical_demo_6min.mp4"
    print(f"[3/3] Encoding to standard MP4: {final_mp4}...")
    cmd = [
        str(FFMPEG_EXE),
        "-y",
        "-i",
        raw_video,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        str(final_mp4),
    ]
    subprocess.run(cmd, check=True)
    print(f"[DONE] Technical Demo video ready at: {final_mp4}")
    return final_mp4


if __name__ == "__main__":
    record_technical_demo()
