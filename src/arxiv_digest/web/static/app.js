async function pollRun(runId) {
  const statusEl = document.getElementById("run-status");
  const messageEl = document.getElementById("run-message");
  const response = await fetch(`/api/runs/${runId}`);
  const payload = await response.json();
  if (statusEl) statusEl.textContent = payload.status;
  if (messageEl) messageEl.textContent = payload.status_message || "";
  if (payload.status === "succeeded" && payload.report_url) {
    window.location.href = payload.report_url;
    return;
  }
  if (payload.status !== "failed") {
    window.setTimeout(() => pollRun(runId), 3000);
  }
}

async function startRun(button) {
  const force = button.dataset.force === "true";
  const tokenRequired = button.dataset.tokenRequired === "true";
  let headers = { "Content-Type": "application/json" };
  if (force || tokenRequired) {
    const token = window.prompt("WEB_ADMIN_TOKEN");
    if (!token) return;
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch("/api/run", {
    method: "POST",
    headers,
    body: JSON.stringify({
      profile: button.dataset.runProfile,
      provider: button.dataset.runProvider,
      force,
    }),
  });
  const payload = await response.json();
  if (!response.ok) {
    window.alert(payload.detail || "Run failed to start.");
    return;
  }
  if (payload.status_url) {
    window.location.href = `/`;
  } else {
    window.location.href = `/reports/today?profile=${button.dataset.runProfile}`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const statusPanel = document.querySelector("[data-run-id]");
  if (statusPanel) {
    pollRun(statusPanel.dataset.runId);
  }
  document.querySelectorAll("[data-run-profile]").forEach((button) => {
    button.addEventListener("click", () => startRun(button));
  });
});
