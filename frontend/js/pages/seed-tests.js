import { api } from "../api.js";
import { escapeHtml, showToast, statusBadge } from "../components/modals.js";

export async function renderSeedTestsPage(container) {
  container.innerHTML = `<div class="loading-state">Loading Seed Test Lab...</div>`;
  try {
    const [accountsData, testsData] = await Promise.all([
      api.listSeedAccounts(),
      api.listSeedTests(),
    ]);
    const accounts = accountsData.accounts || [];
    const tests = testsData.items || [];

    const accountOptions = accounts
      .map(
        (a) =>
          `<option value="${escapeHtml(a.handle_or_address)}" data-channel="${escapeHtml(a.channel)}">
            [${escapeHtml(a.channel.toUpperCase())}] ${escapeHtml(a.handle_or_address)} (${escapeHtml(a.label)})
          </option>`
      )
      .join("");

    const testRows = tests
      .map(
        (t) => `
      <tr>
        <td><code>${escapeHtml(t.id)}</code></td>
        <td><span class="badge badge-info">${escapeHtml(t.channel.toUpperCase())}</span><br/><small>${escapeHtml(t.recipient_address)}</small></td>
        <td><code>${escapeHtml(t.execution_mode)}</code></td>
        <td>${statusBadge(t.status)}</td>
        <td>
          <small><a href="${escapeHtml(t.tracking_url)}" target="_blank" rel="noopener">${escapeHtml(t.tracking_token)} &nearr;</a></small><br/>
          <span class="badge badge-info">Clicks: ${(t.tracking_events || []).length}</span>
          <span class="badge badge-success">Replies: ${(t.reply_events || []).length}</span>
        </td>
        <td>${t.is_genuine_external_execution ? '<span class="badge badge-success">GENUINE EXTERNAL PROOF</span>' : '<span class="badge badge-synthetic">LOCAL DRY_RUN / SIMULATED</span>'}</td>
        <td><small>${escapeHtml(t.error_recovery_notes || "None")}</small></td>
        <td>
          <div style="display:flex;gap:5px;flex-wrap:wrap;">
            <button class="btn btn-secondary btn-sm sim-click-btn" data-token="${escapeHtml(t.tracking_token)}">Test Tracking Click</button>
            <button class="btn btn-teal btn-sm log-reply-btn" data-id="${escapeHtml(t.id)}" data-addr="${escapeHtml(t.recipient_address)}">Log Reply</button>
          </div>
        </td>
      </tr>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <span class="card-title">Seed Test Lab — Controlled 3-Channel Proof (Zero Real Creator Outreach)</span>
        </div>
        <p style="margin-bottom:14px;color:#475569;">
          All seed tests enforce strict allowlisting against participant-owned accounts. Sending to any non-allowlisted address or real creator is deterministically blocked. Default mode is <code>DRY_RUN</code>.
        </p>

        <form id="seed-test-form">
          <div class="form-grid">
            <div class="form-group">
              <label for="seed-account-select">Select Allowlisted Owned Test Account</label>
              <select id="seed-account-select" class="form-control">
                ${accountOptions}
              </select>
            </div>
            <div class="form-group">
              <label for="seed-mode">Execution Mode</label>
              <select id="seed-mode" class="form-control">
                <option value="DRY_RUN">DRY_RUN (Default Safe Log)</option>
                <option value="MANUAL_COMPLIANT_SEND">MANUAL_COMPLIANT_SEND (Requires Approval & Proof)</option>
              </select>
            </div>
            <div class="form-group">
              <label for="seed-proof-path">Evidence Attachment Path / URL (Optional)</label>
              <input type="text" id="seed-proof-path" class="form-control" placeholder="e.g. output/seed_proof_email.png" />
            </div>
          </div>
          <div class="form-group" style="margin-bottom:10px;">
            <label for="seed-msg-preview">Outreach Sequence Message Preview</label>
            <textarea id="seed-msg-preview" class="form-control" rows="3">Hi [Owned Test Account] — Seed test verification of Step 1 sequence with tracking link and opt-out.</textarea>
          </div>
          <div style="display:flex;gap:16px;align-items:center;margin-bottom:12px;flex-wrap:wrap;">
            <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;">
              <input type="checkbox" id="seed-explicit-approval" />
              Explicit Approval for Owned-Account Test Send
            </label>
            <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;">
              <input type="checkbox" id="seed-sim-recovery" />
              Simulate Transient Delivery Failure & Automatic Idempotent Recovery
            </label>
          </div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <button type="submit" class="btn btn-primary">Execute Owned-Account Seed Test</button>
            <button type="button" class="btn btn-danger" id="btn-test-allowlist-block">Test Unauthorised Recipient Block (Security Proof)</button>
          </div>
        </form>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Seed Test Runs, Tracking Link Events & Reply Logs (${tests.length})</span>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Channel & Recipient</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Tracking Token & Events</th>
                <th>Evidence Classification</th>
                <th>Error Recovery</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${testRows}
            </tbody>
          </table>
        </div>
      </div>
    `;

    document.getElementById("seed-test-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const sel = document.getElementById("seed-account-select");
      const opt = sel.options[sel.selectedIndex];
      const recipient_address = sel.value;
      const channel = opt.dataset.channel || "email";
      const execution_mode = document.getElementById("seed-mode").value;
      const evidence_attachment_path = document.getElementById("seed-proof-path").value.trim() || null;
      const message_preview = document.getElementById("seed-msg-preview").value;
      const explicit_approval = document.getElementById("seed-explicit-approval").checked;
      const simulate_failure_recovery = document.getElementById("seed-sim-recovery").checked;

      try {
        await api.createSeedTest({
          channel,
          recipient_address,
          message_preview,
          execution_mode,
          explicit_approval,
          evidence_attachment_path,
          simulate_failure_recovery,
        });
        showToast(`Seed test logged on ${channel} (${execution_mode})!`, "success");
        await renderSeedTestsPage(container);
      } catch (err) {
        showToast(err.message, "error");
      }
    });

    document.getElementById("btn-test-allowlist-block")?.addEventListener("click", async () => {
      try {
        await api.createSeedTest({
          channel: "email",
          recipient_address: "real.creator.unauthorised@youtube-creator.com",
          message_preview: "Should be blocked",
          execution_mode: "DRY_RUN",
        });
      } catch (err) {
        showToast(`Allowlist Guard Verified! Blocked with: ${err.message}`, "success");
      }
    });

    container.querySelectorAll(".sim-click-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api.triggerSeedClick(btn.dataset.token);
          showToast(`Logged tracking link click for token ${btn.dataset.token}!`, "success");
          await renderSeedTestsPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });

    container.querySelectorAll(".log-reply-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api.recordSeedReply(btn.dataset.id, {
            sender_address: btn.dataset.addr,
            reply_text: "Confirmed receipt of 3-step seed test sequence and tracking link.",
            is_genuine_external_reply: false,
          });
          showToast(`Associated reply event with seed test ${btn.dataset.id}!`, "success");
          await renderSeedTestsPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Seed Test Lab: ${escapeHtml(err.message)}</div>`;
  }
}
