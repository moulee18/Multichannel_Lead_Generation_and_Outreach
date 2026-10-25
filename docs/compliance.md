# Privacy, Platform & Outbound Compliance

- **Zero Real Creator Outreach**: During the assessment, outreach is strictly restricted to participant-owned allowlisted test accounts in the Seed Test Lab (`backend/app/security/permissions.py`). Any attempt to dispatch a test to a non-allowlisted address raises `IntegrityViolationError` (HTTP 403).
- **Marketing & Privacy Laws**: All outreach templates include explicit sender identity (`Arjun Mehta — Independent Growth Assessment Participant`) and a clear opt-out line (`Reply 'stop' or 'opt out' at any time`) in compliance with CAN-SPAM, GDPR, and India's DPDP Act.
- **No Impersonation**: Never claims to be an IncuBrix employee.
- **AI Hallucination Guard**: Every intelligence profile and outreach message is deterministically checked against `product_capabilities.json` and stored `Evidence` records.
