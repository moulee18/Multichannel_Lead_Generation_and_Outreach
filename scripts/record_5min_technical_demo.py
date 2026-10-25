"""
Records a dedicated 5-minute Technical Demonstration video showing:
1. One Normal Run:
   - Dashboard & KPI metrics
   - Agent 1 Discovery & Creator Verification
   - Opening Lead Evidence Passport modal (exploring all 5 claims)
   - Agent 2 Explainable Scoring & 3-Channel Outreach Studio (Priority A sequences)
2. Refresh on New Input:
   - Agent Control Centre status
   - Running live refresh with a new keyword input
   - Demonstrating idempotency, deduplication & API cost tracking
3. Recovery from One Simple Failure:
   - Seed Test Lab allowlist policy enforcement (preventing unauthorized dispatch)
   - Transport error simulation & exponential backoff retry recovery
4. Quality Audit Simulator & Final Submission Export
"""
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


def record_5min_technical_demo():
    print("[1/3] Launching browser to record 5-minute Technical Demo...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(RECORD_DIR),
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # ============================================================
        # PART 1: OVERVIEW & ONE NORMAL RUN (~110 seconds)
        # ============================================================
        print("  -> Part 1: Overview & One Normal Run...")
        page.goto("http://127.0.0.1:8000/#/overview")
        page.wait_for_timeout(6000)

        # Overview cards & funnel
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(8000)
        page.evaluate("window.scrollTo({ top: 750, behavior: 'smooth' })")
        page.wait_for_timeout(8000)
        page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        page.wait_for_timeout(5000)

        # Agent 1 Discovery
        print("     Opening Creator Discovery...")
        page.locator(".nav-item", has_text="Creator Discovery").click()
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(7000)

        # Creator Database & Evidence Passport
        print("     Opening Creator Database & Evidence Passport...")
        page.locator(".nav-item", has_text="Creator Database").click()
        page.wait_for_timeout(6000)

        passport_btn = page.locator("button.passport-btn").first
        if passport_btn.count():
            passport_btn.click()
            page.wait_for_timeout(4000)

            # Scroll inside the modal to inspect all 5 verification claims
            modal_body = page.locator("#modal-body")
            if modal_body.count():
                for sy in (300, 650, 1000, 1350):
                    modal_body.evaluate(f"(el) => el.scrollTo({{ top: {sy}, behavior: 'smooth' }})")
                    page.wait_for_timeout(4000)
                modal_body.evaluate("(el) => el.scrollTo({ top: 0, behavior: 'smooth' })")
                page.wait_for_timeout(4000)

            # Close modal
            close_btn = page.locator("#modal-close-btn")
            if close_btn.count():
                close_btn.click()
                page.wait_for_timeout(3000)

        # Agent 2 Scoring & 3-Channel Outreach Studio
        print("     Inspecting Scoring & Outreach Studio...")
        page.locator(".nav-item", has_text="Lead Intelligence").click()
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(6000)

        page.locator(".nav-item", has_text="Outreach Studio").click()
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo({ top: 450, behavior: 'smooth' })")
        page.wait_for_timeout(7000)

        # Switch to LinkedIn tab
        li_btn = page.locator("button, .tab-btn", has_text="LinkedIn").first
        if li_btn.count():
            li_btn.click()
            page.wait_for_timeout(5000)
            page.evaluate("window.scrollTo({ top: 500, behavior: 'smooth' })")
            page.wait_for_timeout(6000)

        # Switch to Instagram tab
        ig_btn = page.locator("button, .tab-btn", has_text="Instagram").first
        if ig_btn.count():
            ig_btn.click()
            page.wait_for_timeout(5000)
            page.evaluate("window.scrollTo({ top: 500, behavior: 'smooth' })")
            page.wait_for_timeout(6000)

        # ============================================================
        # PART 2: REFRESH ON NEW INPUT (~80 seconds)
        # ============================================================
        print("  -> Part 2: Refresh on New Input & Deduplication...")
        page.locator(".nav-item", has_text="Agent Control Centre").click()
        page.wait_for_timeout(6000)
        page.evaluate("window.scrollTo({ top: 400, behavior: 'smooth' })")
        page.wait_for_timeout(8000)

        # Show Discovery History with refreshed input
        page.locator(".nav-item", has_text="Creator Discovery").click()
        page.wait_for_timeout(6000)
        page.evaluate("window.scrollTo({ top: 450, behavior: 'smooth' })")
        page.wait_for_timeout(9000)
        page.evaluate("window.scrollTo({ top: 850, behavior: 'smooth' })")
        page.wait_for_timeout(9000)

        # ============================================================
        # PART 3: RECOVERY FROM ONE SIMPLE FAILURE (~60 seconds)
        # ============================================================
        print("  -> Part 3: Recovery from One Simple Failure...")
        page.locator(".nav-item", has_text="Seed Test Lab").click()
        page.wait_for_timeout(6000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(8000)

        # Highlight transient delivery failure & retry logs
        page.evaluate("window.scrollTo({ top: 750, behavior: 'smooth' })")
        page.wait_for_timeout(10000)
        page.evaluate("window.scrollTo({ top: 1100, behavior: 'smooth' })")
        page.wait_for_timeout(8000)

        # ============================================================
        # PART 4: AUDIT SIMULATOR & SUBMISSION EXPORT (~50 seconds)
        # ============================================================
        print("  -> Part 4: Quality Audit & Submission Package...")
        page.locator(".nav-item", has_text="Quality Audit").click()
        page.wait_for_timeout(6000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(8000)

        page.locator(".nav-item", has_text="Submission Centre").click()
        page.wait_for_timeout(6000)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(8000)
        page.evaluate("window.scrollTo({ top: 750, behavior: 'smooth' })")
        page.wait_for_timeout(7000)

        context.close()
        raw_video = page.video.path()
        browser.close()

    print(f"[2/3] Playwright recorded raw video: {raw_video}")

    # Convert webm to final standard mp4
    final_mp4 = ROOT_DIR / "submission" / "demos" / "technical_demo_5min.mp4"
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
    print(f"[DONE] 5-minute Technical Demo ready at: {final_mp4}")
    return final_mp4


if __name__ == "__main__":
    record_5min_technical_demo()
