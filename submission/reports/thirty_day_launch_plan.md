# IncuBrix 30-Day Creator Acquisition & Multi-Channel Launch Kit

## 1. Executive Summary & Target Segments
This launch kit enables IncuBrix to begin compliant, evidence-backed creator outreach on **Day 1 (next Monday)** and rerun weekly refresh cycles automatically.

- **Segment 1 — Podcasters & Video Podcasters (40% share)**: Weekly long-form shows (45–90 min) monetising via sponsorships or memberships that need rapid short-clip repurposing and captioning.
- **Segment 2 — YouTubers & Video-First Creators (35% share)**: Educational/business YouTube channels publishing 2+ long-form videos/60d or 8+ items/30d with post-production editing backlogs.
- **Segment 3 — Expert-Led Creators: Coaches, Consultants & Educators (25% share)**: High-LTV course/coaching operators needing consistent multi-channel authority clips across YouTube, LinkedIn, and Instagram.

---

## 2. Channel Strategy & Safe Daily Volumes
| Channel | Role in Sequence | Safe Daily Volume / Rep | Weekly Volume (5 Days) | 30-Day Volume (22 Workdays) | Compliance & Platform Rules |
|---|---|---:|---:|---:|---|
| **Business Email** | Primary Channel (70% of leads) | 35–45 emails/day (warmed domain) | 200 emails/week | 880 emails/month | CAN-SPAM / GDPR / India DPDP compliant; SPF/DKIM/DMARC configured; explicit sender identity & 1-click/reply opt-out. |
| **LinkedIn (Manual Assisted)** | Primary/Backup for Coaches & B2B Podcasters | 15–20 personalised notes/day | 85 messages/week | 375 messages/month | Zero unauthorized scraping or bulk automation; manual review & send from Outreach Studio queue. |
| **Instagram Business DM / Guest Desk** | Backup for Video-First & Lifestyle Podcasters | 10–15 contextual DMs/day | 60 messages/week | 260 messages/month | Manual contextual outreach referencing specific recent Reel/Episode; no automated DM bots. |

---

## 3. Week-by-Week Execution Plan (Days 1–30)

### Week 1 (Days 1–7): Priority A Launch & Baseline Calibration
- **Monday (Day 1)**: Verify domain authentication (SPF, DKIM, DMARC) and launch Step 1 (First Contact) to the top **25 Priority A** creators across Email, LinkedIn, and Instagram.
- **Tuesday–Wednesday (Days 2–3)**: Dispatch cohort 1 of Priority B leads (35 emails/day + 15 LinkedIn + 10 Instagram). Log all opens/clicks/replies in GrowthOS.
- **Thursday (Day 4)**: Trigger **Follow-Up 1 (Step 2)** for non-responding Priority A leads referencing their latest episode clip opportunity.
- **Friday (Day 5)**: Run weekly `Smart Refresh` (`python scripts/run_refresh.py`) to ingest new creator uploads and verify fresh 30-day evidence.

### Week 2 (Days 8–14): Multi-Channel Follow-Up & Segment A/B Review
- **Monday (Day 8)**: Dispatch **Follow-Up 2 (Step 3 — Breakup/Value Offer)** for Day-1 Priority A non-responders; switch non-email responders to their verified Backup Channel.
- **Tuesday–Thursday (Days 9–11)**: Scale daily email volume to 45/day as domain reputation holds (<0.1% spam complaint rate, <1.5% bounce rate).
- **Friday (Day 12)**: Review reply rates by segment (Podcasters vs Coaches vs YouTubers) and promote top-performing hooks into Agent 2 templates.

### Week 3 (Days 15–21): Backlog Wedge Campaign & Pipeline Refresh
- **Monday–Wednesday (Days 15–17)**: Run the **"1-Episode Repurposing Wedge"** offer for high-scoring Priority B creators (offering a concrete walkthrough using their most recent long-form video).
- **Thursday (Day 18)**: Audit 20 random active leads via Agent 3's Random Audit Simulator to ensure >=90% contact accuracy and <30-day evidence freshness.
- **Friday (Day 19)**: Execute weekly Smart Refresh and replenish Priority A queue with newly discovered creators.

### Week 4 (Days 22–30): Conversion Optimization & Month-2 Scale Handover
- **Monday–Wednesday (Days 22–24)**: Follow up with warm "not right now / check back next month" replies and book live IncuBrix workflow demos.
- **Thursday (Day 25)**: Export monthly CRM attribution report (`leads.csv` + `runtime_costs.csv` + channel conversion matrix).
- **Friday (Day 30)**: Finalise Month-2 channel mix allocation based on verified reply-to-meeting conversion data.

---

## 4. Responsible Owners, Tools & Budget
| Workstream | Responsible Owner | Tools Used | Estimated 30-Day Budget (USD) |
|---|---|---|---:|
| **Discovery, Verification & Refresh** | Growth Engineer | IncuBrix GrowthOS + YouTube Data API v3 + Public Podcast RSS | $0 (Free tier API quotas) |
| **AI Analysis & Draft Generation** | Growth Engineer | GrowthOS Agent 2 (Deterministic / Optional Gemini Flash or GPT-4o-mini) | $0 – $15/mo (optional LLM tokens) |
| **Email Sending & Deliverability** | Growth Engineer / SDR | Google Workspace / Custom Domain Mailbox (2 warmed inboxes) | $14 – $28/mo |
| **LinkedIn & Instagram Assisted Outreach** | SDR / Growth Associate | GrowthOS Outreach Studio + Native Platform Business Profiles | $0 |
| **Total Estimated 30-Day Budget** | | | **$14 – $43 / month** |

---

## 5. Expected Reply & Meeting Rates (With Reasoning)
- **Email Sequence (3 Steps)**:
  - **Expected Positive/Neutral Reply Rate**: **6.5% – 9.5%** (3.2% – 4.5% qualified positive reply rate).
  - **Expected Demo/Meeting Rate**: **2.0% – 3.0%** of contacted leads (~18–26 meetings per 880 leads).
  - *Reasoning*: Generic cold outreach averages <1% reply rate, whereas every lead in GrowthOS has verified recent activity (30d/60d), verified monetization, and a message citing their exact recent video title and production need.
- **LinkedIn Assisted Sequence**:
  - **Expected Acceptance + Reply Rate**: **12.0% – 16.0%** (4.0% – 5.5% positive reply rate).
  - **Expected Demo/Meeting Rate**: **2.5% – 3.8%** (~9–14 meetings per 375 leads).
  - *Reasoning*: Expert-led creators (coaches, consultants, B2B podcasters) actively use LinkedIn for distribution and respond strongly to peer-level workflow notes.
- **Instagram Business DM Sequence**:
  - **Expected Reply Rate**: **8.0% – 12.0%** (~2.0% meeting conversion, ~5–8 meetings per 260 leads).
  - *Reasoning*: Video-first creators check Instagram business requests when messages reference a specific recent Reel/episode rather than a generic pitch.

---

## 6. Key Assumptions, Risks & Mitigations
| Risk | Impact | Mitigation Built into GrowthOS |
|---|---|---|
| **Email deliverability degradation or bounces** | High | Never guess emails; only contact verified public business emails; cap per-inbox volume at 35–45/day. |
| **Platform account restrictions on LinkedIn / Instagram** | High | Strictly forbid unauthorized browser bots/scrapers; use human-in-the-loop manual send from Outreach Studio. |
| **Stale creator references (>30 days old)** | Medium | Agent 3 blocks any outreach citing evidence older than 30 days; weekly Smart Refresh updates recent uploads. |
| **AI hallucinated product claims** | High | AI Hallucination Guard deterministically cross-checks every draft against `product_capabilities.json` and stored Evidence IDs. |
