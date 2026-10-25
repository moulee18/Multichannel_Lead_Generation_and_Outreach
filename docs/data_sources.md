# Permitted Data Sources & Collection Engineering

1. **Official YouTube Data API v3 (`backend/app/integrations/youtube_api.py`)**:
   - Uses `/search`, `/channels`, `/playlistItems`, and `/videos` endpoints.
   - Extracts stable `UC...` channel IDs, upload playlist items, ISO-8601 durations, and publication dates.
   - Logs all quota units, HTTP status codes, latencies, and errors in `api_usage`.
2. **Public Podcast Discovery & XML RSS Feeds (`backend/app/integrations/podcast_sources.py`)**:
   - Uses Apple's public iTunes Search API (`https://itunes.apple.com/search?media=podcast`) to discover podcasts and parses public XML RSS feeds for episode publication timestamps, durations, show descriptions, and `<itunes:email>` business contacts.
3. **Permitted Creator Business Websites (`backend/app/integrations/permitted_web_sources.py`)**:
   - Verifies `robots.txt` permission via `urllib.robotparser` before fetching any creator-owned public business page.
   - Never bypasses logins, paywalls, or anti-bot controls.
