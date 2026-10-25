import { api } from "../api.js";
import { escapeHtml, showToast, statusBadge } from "../components/modals.js";

let selectedCreatorId = null;

export async function renderOutreachPage(container) {
  container.innerHTML = `<div class="loading-state">Loading Outreach Studio...</div>`;
  try {
    const priorityAData = await api.getPriorityALeads(true);
    const leads = priorityAData.items || [];

    if (!selectedCreatorId && leads.length > 0) {
      selectedCreatorId = leads[0].creator_id;
    }

    let outreachData = null;
    if (selectedCreatorId) {
      outreachData = await api.getCreatorOutreach(selectedCreatorId);
    }

    const optionsHtml = leads
      .map(
        (l) =>
          `<option value="${escapeHtml(l.creator_id)}" ${l.creator_id === selectedCreatorId ? "selected" : ""}>
            #${l.rank_position} — ${escapeHtml(l.creator_name)} (${escapeHtml(l.priority_tier)} | Score: ${l.total_score})
          </option>`
      )
      .join("");

    const messagesHtml = (outreachData?.messages || [])
      .map(
        (m) => `
      <div class="card">
        <div class="card-header">
          <div>
            <span class="badge badge-info">${escapeHtml(m.channel.toUpperCase())}</span>
            <strong style="margin-left:6px;">Step ${m.step_number}: ${escapeHtml(m.step_label)}</strong>
            <small style="margin-left:8px;color:#64748b;">Version v${m.version_number}</small>
          </div>
          <div>
            ${m.validation_passed ? '<span class="badge badge-success">AI Hallucination Guard: PASSED</span>' : '<span class="badge badge-danger">AI Hallucination Guard: FLAGGED</span>'}
            ${statusBadge(m.approval_status)}
          </div>
        </div>

        <p style="font-size:12px;color:#475569;margin-bottom:8px;">
          <strong>Referenced Recent Content:</strong>
          <a href="${escapeHtml(m.referenced_content_url)}" target="_blank" rel="noopener">${escapeHtml(m.referenced_content_title)} &nearr;</a>
          | <strong>Evidence IDs:</strong> <code>${escapeHtml((m.cited_evidence_ids || []).join(", "))}</code>
          | <strong>Capabilities:</strong> <code>${escapeHtml((m.referenced_capability_keys || []).join(", "))}</code>
        </p>

        ${
          m.validation_flags && m.validation_flags.length
            ? `<div style="background:#fee2e2;color:#b91c1c;padding:8px 12px;border-radius:6px;margin-bottom:10px;font-size:12px;">
                <strong>Hallucination / Compliance Flags:</strong> ${escapeHtml(m.validation_flags.join(" | "))}
              </div>`
            : ""
        }

        <form class="msg-edit-form" data-id="${escapeHtml(m.id)}">
          ${
            m.subject !== null
              ? `<div class="form-group" style="margin-bottom:8px;">
                  <label>Subject Line</label>
                  <input type="text" class="form-control msg-subj" value="${escapeHtml(m.subject || "")}" />
                </div>`
              : ""
          }
          <div class="form-group" style="margin-bottom:10px;">
            <label>Message Body (Includes Sender Identity & Opt-Out)</label>
            <textarea class="form-control msg-body" rows="6">${escapeHtml(m.body)}</textarea>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button type="submit" class="btn btn-primary btn-sm">Save Edit & Re-Validate</button>
            <button type="button" class="btn btn-teal btn-sm msg-approve-btn" data-id="${escapeHtml(m.id)}">Approve Draft</button>
          </div>
        </form>
      </div>
    `
      )
      .join("");

    container.innerHTML = `
      <div class="card">
        <div class="card-header">
          <span class="card-title">Outreach Studio — Multi-Channel 3-Step Sequences</span>
          <div style="display:flex;gap:8px;">
            <button class="btn btn-secondary btn-sm" id="btn-regen-creator" ${!selectedCreatorId ? "disabled" : ""}>Regenerate Selected Creator</button>
            <button class="btn btn-primary btn-sm" id="btn-gen-all-pa">Generate All Priority A Sequences</button>
          </div>
        </div>

        <div class="form-grid">
          <div class="form-group">
            <label for="outreach-creator-select">Select Priority A Creator</label>
            <select id="outreach-creator-select" class="form-control">
              ${optionsHtml || '<option value="">No Priority A leads available yet</option>'}
            </select>
          </div>
          <div class="form-group">
            <label>Selected Channel Decision</label>
            <div style="padding:8px 0;">
              Primary: <span class="badge badge-success">${escapeHtml(outreachData?.primary_channel || "N/A")}</span>
              | Backup: <span class="badge badge-info">${escapeHtml(outreachData?.backup_channel || "None Verified")}</span>
            </div>
          </div>
        </div>
      </div>

      ${messagesHtml || '<div class="empty-state">No outreach drafts generated for this creator yet. Click "Generate All Priority A Sequences" above.</div>'}
    `;

    document.getElementById("outreach-creator-select")?.addEventListener("change", (e) => {
      selectedCreatorId = e.target.value;
      renderOutreachPage(container);
    });

    document.getElementById("btn-regen-creator")?.addEventListener("click", async () => {
      if (!selectedCreatorId) return;
      showToast("Regenerating 3-channel sequences for creator...", "info");
      try {
        await api.generateOutreach({
          creator_id: selectedCreatorId,
          channels: ["email", "linkedin", "instagram"],
          force_regenerate: true,
        });
        showToast("Regenerated 9 outreach drafts (3 channels x 3 steps)!", "success");
        await renderOutreachPage(container);
      } catch (err) {
        showToast(err.message, "error");
      }
    });

    document.getElementById("btn-gen-all-pa")?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      showToast("Generating 3-step sequences across Email, LinkedIn & Instagram for all Priority A leads...", "info");
      try {
        const res = await api.generateOutreach({
          channels: ["email", "linkedin", "instagram"],
          force_regenerate: false,
        });
        showToast(`Generated ${res.generated_count} drafts across ${res.creators_processed} Priority A creators!`, "success");
        await renderOutreachPage(container);
      } catch (err) {
        showToast(err.message, "error");
        e.target.disabled = false;
      }
    });

    container.querySelectorAll(".msg-edit-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const mid = form.dataset.id;
        const subjEl = form.querySelector(".msg-subj");
        const bodyEl = form.querySelector(".msg-body");
        try {
          const updated = await api.patchOutreachMessage(mid, {
            subject: subjEl ? subjEl.value : null,
            body: bodyEl.value,
            edit_notes: "Manual edit via Outreach Studio",
          });
          if (updated.validation_passed) {
            showToast(`Saved v${updated.version_number} — AI Hallucination Guard PASSED!`, "success");
          } else {
            showToast(`Saved v${updated.version_number} — Guard flagged: ${updated.validation_flags.join(", ")}`, "error");
          }
          await renderOutreachPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });

    container.querySelectorAll(".msg-approve-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api.reviewOutreachMessage(btn.dataset.id, { approval_status: "APPROVED" });
          showToast("Message approved!", "success");
          await renderOutreachPage(container);
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading Outreach Studio: ${escapeHtml(err.message)}</div>`;
  }
}
