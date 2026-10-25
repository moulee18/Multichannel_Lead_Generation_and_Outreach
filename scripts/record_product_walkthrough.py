"""
Generates the 4-minute Product Walkthrough video recording.
Navigates through https://www.incubrix.com and the local IncuBrix GrowthOS app,
demonstrating the 5 Product Observations and 3 Growth Opportunities.
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


def record_product_walkthrough():
    print("[1/3] Launching browser to record 4-minute Product Walkthrough...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(RECORD_DIR),
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Phase 1: 0:00 - 1:00 Intro & Official Incubrix Platform
        print("  -> Section 1: Intro & https://www.incubrix.com (45s)...")
        try:
            page.goto("https://www.incubrix.com", wait_until="load", timeout=15000)
        except Exception:
            page.goto("https://www.incubrix.com", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(4000)

        # Smooth scrolling through Incubrix homepage
        for scroll_y in range(300, 2400, 350):
            page.evaluate(f"window.scrollTo({{ top: {scroll_y}, behavior: 'smooth' }})")
            page.wait_for_timeout(2500)

        # Scroll back up to features
        page.evaluate("window.scrollTo({ top: 600, behavior: 'smooth' })")
        page.wait_for_timeout(4000)

        # Phase 2: 1:00 - 2:15 Switch to IncuBrix GrowthOS Product Insights
        print("  -> Section 2: 5 Product Observations & Workflow Need Analysis (75s)...")
        page.goto("http://127.0.0.1:8000/#/intelligence")
        page.wait_for_timeout(3000)

        # Highlight Product ICP & Workflow Needs
        page.evaluate("window.scrollTo({ top: 300, behavior: 'smooth' })")
        page.wait_for_timeout(6000)

        # Navigate to Verification Queue to show Real-world Creator Need & Latency
        page.locator(".nav-item", has_text="Verification Queue").click()
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo({ top: 400, behavior: 'smooth' })")
        page.wait_for_timeout(6000)

        # Phase 3: 2:15 - 3:30 3 High-Impact Growth Opportunities & Sample Clip Hook
        print("  -> Section 3: 3 High-Impact Growth Opportunities (75s)...")
        page.locator(".nav-item", has_text="Lead Intelligence").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 700, behavior: 'smooth' })")
        page.wait_for_timeout(6000)

        # Switch to Outreach Studio to demonstrate the Sample Clip Teaser & Multi-Channel Angles
        page.locator(".nav-item", has_text="Outreach Studio").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 300, behavior: 'smooth' })")
        page.wait_for_timeout(6000)

        # Click on LinkedIn & Instagram tabs to demonstrate multi-channel land-and-expand
        li_btn = page.locator("button, .tab-btn", has_text="LinkedIn").first
        if li_btn.count():
            li_btn.click()
            page.wait_for_timeout(5000)

        ig_btn = page.locator("button, .tab-btn", has_text="Instagram").first
        if ig_btn.count():
            ig_btn.click()
            page.wait_for_timeout(5000)

        # Phase 4: 3:30 - 4:00 Conclusion & Link to GrowthOS Engine
        print("  -> Section 4: Conclusion & Overview Dashboard (45s)...")
        page.locator(".nav-item", has_text="Overview").click()
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo({ top: 400, behavior: 'smooth' })")
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        page.wait_for_timeout(4000)

        context.close()
        raw_video = page.video.path()
        browser.close()

    print(f"[2/3] Playwright recorded raw video: {raw_video}")

    # Convert webm to final standard mp4
    final_mp4 = ROOT_DIR / "submission" / "demos" / "product_walkthrough_4min.mp4"
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
    print(f"[DONE] Product Walkthrough video ready at: {final_mp4}")
    return final_mp4


if __name__ == "__main__":
    record_product_walkthrough()
