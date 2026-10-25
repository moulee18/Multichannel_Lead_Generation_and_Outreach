from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_full_application_api_and_e2e_workflow():
    with TestClient(app) as client:
        # 1. Health check & static frontend shell
        h_resp = client.get("/api/health")
        assert h_resp.status_code == 200
        assert h_resp.json()["status"] == "healthy"

        html_resp = client.get("/")
        assert html_resp.status_code == 200
        assert "IncuBrix GrowthOS" in html_resp.text

        # 2. Authentication endpoint
        login_resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "incubrix-local-admin"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Run full pipeline via REST API
        pipe_resp = client.post(
            "/api/pipeline/run",
            headers=headers,
            json={
                "keyword": "video podcast creator",
                "category": "Podcaster / Video Podcaster",
                "max_candidates": 35,
                "source": "synthetic_demo",
                "run_mode": "synthetic_demo",
            },
        )
        assert pipe_resp.status_code == 200
        job_data = pipe_resp.json()
        assert job_data["status"] == "COMPLETED"
        assert job_data["passed_count"] >= 30

        # 4. Verify Creators & Lead Evidence Passport endpoint
        creators_resp = client.get("/api/creators?status=QUALIFIED&page_size=50", headers=headers)
        assert creators_resp.status_code == 200
        assert creators_resp.json()["total"] >= 30
        creators_list = creators_resp.json()["items"]
        assert len(creators_list) >= 30
        first_id = creators_list[0]["id"]

        passport_resp = client.get(f"/api/creators/{first_id}/evidence", headers=headers)
        assert passport_resp.status_code == 200
        passport = passport_resp.json()
        assert len(passport["evidence_claims"]) >= 5

        # 5. Explainable Lead Scoring & Contact Channel Explainer endpoints
        score_resp = client.get(f"/api/leads/{first_id}/score", headers=headers)
        assert score_resp.status_code == 200
        assert score_resp.json()["total_score"] > 0

        chan_resp = client.get(f"/api/leads/{first_id}/channels", headers=headers)
        assert chan_resp.status_code == 200
        assert chan_resp.json()["has_verified_channel"] is True

        # 6. Priority A & Outreach Studio endpoints
        pa_resp = client.get("/api/leads/priority-a", headers=headers)
        assert pa_resp.status_code == 200
        assert len(pa_resp.json()["items"]) == 25

        outreach_resp = client.get(f"/api/outreach/creators/{first_id}", headers=headers)
        assert outreach_resp.status_code == 200
        messages = outreach_resp.json()["messages"]
        assert len(messages) >= 9

        # 7. Smart Refresh endpoint (idempotent duplicate prevention)
        ref_resp = client.post(
            "/api/pipeline/refresh",
            headers=headers,
            json={"keyword": "video podcast", "source": "synthetic_demo", "max_candidates": 10},
        )
        assert ref_resp.status_code == 200
        ref_data = ref_resp.json()
        assert ref_data["duplicates_prevented_count"] >= 10

        # 8. Unauthorised outbound seed test recipient MUST return 403
        blocked_seed = client.post(
            "/api/seed-tests",
            headers=headers,
            json={
                "channel": "email",
                "recipient_address": "unauthorised.real.creator@domain.com",
                "message_preview": "Test",
                "execution_mode": "DRY_RUN",
            },
        )
        assert blocked_seed.status_code == 403

        # 9. Exports & file download
        exports_resp = client.get("/api/exports", headers=headers)
        assert exports_resp.status_code == 200
        artifacts = exports_resp.json()["artifacts"]
        assert len(artifacts) > 0
        dl_resp = client.get(artifacts[0]["download_url"], headers=headers)
        assert dl_resp.status_code == 200
        assert len(dl_resp.content) > 0
