let currentReqId = null;
let currentCandId = null;
let suitabilityChart = null;
let timeToFillChart = null;
let preboardingAttritionChart = null;
let currentInterviewId = null;

// Initial loading
document.addEventListener("DOMContentLoaded", () => {

    loadAllRequirements();

    // Candidate list is recruiter-only.
    // Do not load it automatically on the public Career Twin page.

});

// ============================================================
// LEVELUPWARDS PROPOSAL
// RECRUITER APPLICATION PIPELINE
// ============================================================

async function loadRecruiterApplicationPipeline() {

    const container = document.getElementById(
        "recruiter-application-pipeline"
    );

    if (!container) {
        console.warn(
            "recruiter-application-pipeline container not found."
        );
        return;
    }

    container.innerHTML = `
        <div style="
            padding:1rem;
            text-align:center;
            color:var(--text-secondary);
            font-size:0.8rem;
        ">
            Loading application pipeline...
        </div>
    `;

    try {

        const res = await fetch(
            "/api/recruiter/applications"
        );

        if (!res.ok) {
            throw new Error(
                `Failed to load applications: ${res.status}`
            );
        }

        const data = await res.json();

        const applications =
            data.applications || [];

        const stages = [
            "Applied",
            "Screening",
            "Shortlisted",
            "Interviewing",
            "Selected",
            "Offered",
            "Accepted",
            "Joined"
        ];

        const stageColors = {
            Applied: "badge-info",
            Screening: "badge-warning",
            Shortlisted: "badge-success",
            Interviewing: "badge-info",
            Selected: "badge-success",
            Offered: "badge-warning",
            Accepted: "badge-success",
            Joined: "badge-success"
        };

        container.innerHTML = "";

        // ----------------------------------------------------
        // Pipeline summary
        // ----------------------------------------------------

        const summary = document.createElement("div");

        summary.style.display = "grid";
        summary.style.gridTemplateColumns =
            "repeat(auto-fit,minmax(110px,1fr))";
        summary.style.gap = "0.5rem";
        summary.style.marginBottom = "1rem";

        stages.forEach(stage => {

            const count =
                applications.filter(
                    a => a.status === stage
                ).length;

            const box =
                document.createElement("div");

            box.style.padding = "0.7rem";
            box.style.border =
                "1px solid var(--border-color)";
            box.style.borderRadius = "10px";
            box.style.background =
                "rgba(255,255,255,0.02)";
            box.style.textAlign = "center";

            box.innerHTML = `
                <div style="
                    font-size:0.65rem;
                    color:var(--text-secondary);
                    text-transform:uppercase;
                ">
                    ${stage}
                </div>

                <strong style="
                    display:block;
                    margin-top:0.2rem;
                    font-size:1.2rem;
                    color:white;
                ">
                    ${count}
                </strong>
            `;

            summary.appendChild(box);
        });

        container.appendChild(summary);

        // ----------------------------------------------------
        // Application cards
        // ----------------------------------------------------

        if (applications.length === 0) {

            const empty =
                document.createElement("div");

            empty.style.padding = "2rem";
            empty.style.textAlign = "center";
            empty.style.color =
                "var(--text-secondary)";

            empty.innerText =
                "No candidate applications yet.";

            container.appendChild(empty);

            return;
        }

        const list =
            document.createElement("div");

        list.style.display = "flex";
        list.style.flexDirection = "column";
        list.style.gap = "0.6rem";

        applications.forEach(application => {

            const candidate =
                application.candidate || {};

            const requirement =
                application.requirement || {};

            const role =
                application.role || {};

            const card =
                document.createElement("div");

            card.style.padding = "0.85rem";
            card.style.border =
                "1px solid var(--border-color)";
            card.style.borderRadius = "10px";
            card.style.background =
                "rgba(255,255,255,0.02)";

            const matchScore =
                application.match_score != null
                    ? Math.round(
                        application.match_score * 100
                    )
                    : null;

            card.innerHTML = `

                <div style="
                    display:flex;
                    justify-content:space-between;
                    gap:1rem;
                    align-items:flex-start;
                ">

                    <div>

                        <strong style="
                            color:white;
                            font-size:0.9rem;
                        ">
                            ${escapeJobHTML(
                candidate.name ||
                "Unknown Candidate"
            )}
                        </strong>

                        <div style="
                            color:var(--accent-indigo);
                            font-size:0.72rem;
                            margin-top:0.2rem;
                        ">
                            ${escapeJobHTML(
                role.title ||
                requirement.business_outcome ||
                "Open Role"
            )}
                        </div>

                    </div>

                    <span class="badge ${stageColors[
                application.status
                ] || "badge-info"
                }">
                        ${escapeJobHTML(
                    application.status
                )}
                    </span>

                </div>

                <div style="
                    display:grid;
                    grid-template-columns:
                        repeat(auto-fit,minmax(120px,1fr));
                    gap:0.5rem;
                    margin-top:0.7rem;
                    font-size:0.7rem;
                ">

                    <div>
                        <span style="
                            color:var(--text-secondary);
                        ">
                            AI Match
                        </span>

                        <strong style="
                            display:block;
                            margin-top:0.15rem;
                        ">
                            ${matchScore !== null
                    ? `${matchScore}%`
                    : "Pending"
                }
                        </strong>
                    </div>

                    <div>
                        <span style="
                            color:var(--text-secondary);
                        ">
                            Notice
                        </span>

                        <strong style="
                            display:block;
                            margin-top:0.15rem;
                        ">
                            ${candidate.notice_period_days ??
                "-"
                } days
                        </strong>
                    </div>

                    <div>
                        <span style="
                            color:var(--text-secondary);
                        ">
                            Location
                        </span>

                        <strong style="
                            display:block;
                            margin-top:0.15rem;
                        ">
                            ${escapeJobHTML(
                    candidate.location ||
                    "-"
                )}
                        </strong>
                    </div>

                    <div>
                        <span style="
                            color:var(--text-secondary);
                        ">
                            Applied
                        </span>

                        <strong style="
                            display:block;
                            margin-top:0.15rem;
                        ">
                            ${application.applied_at
                    ? new Date(
                        application.applied_at
                    ).toLocaleDateString()
                    : "-"
                }
                        </strong>
                    </div>

                </div>

                <div style="
                    display:flex;
                    gap:0.5rem;
                    margin-top:0.7rem;
                    flex-wrap:wrap;
                ">

                    <button
                        class="btn-secondary"
                        style="
                            font-size:0.7rem;
                            padding:0.4rem 0.7rem;
                        "
                        onclick="
                            inspectCandidate(
                                '${escapeJobAttribute(
                    candidate.id
                )}',
                                '${escapeJobAttribute(
                    requirement.id
                )}'
                            )
                        ">
                        View Candidate Twin
                    </button>

                    ${getNextApplicationStage(
                    application.status
                )
                    ? `
                                <button
                                    class="btn-primary"
                                    style="
                                        font-size:0.7rem;
                                        padding:0.4rem 0.7rem;
                                    "
                                    onclick="
                                        advanceApplicationStage(
                                            '${escapeJobAttribute(
                        application.id
                    )}',
                                            '${escapeJobAttribute(
                        getNextApplicationStage(
                            application.status
                        )
                    )}'
                                        )
                                    ">
                                    Move to ${getNextApplicationStage(
                        application.status
                    )
                    }
                                </button>
                            `
                    : ""
                }

                </div>
            `;

            list.appendChild(card);
        });

        container.appendChild(list);

    } catch (error) {

        console.error(
            "Recruiter application pipeline error:",
            error
        );

        container.innerHTML = `
            <div style="
                padding:1rem;
                border:1px solid var(--border-color);
                border-radius:10px;
                color:var(--danger);
                font-size:0.8rem;
            ">
                Unable to load recruiter applications.

                <button
                    class="btn-secondary"
                    style="
                        margin-left:0.5rem;
                        font-size:0.7rem;
                    "
                    onclick="loadRecruiterApplicationPipeline()">
                    Retry
                </button>
            </div>
        `;
    }
}


// ============================================================
// NEXT APPLICATION STAGE
// ============================================================

function getNextApplicationStage(status) {

    const flow = [
        "Applied",
        "Screening",
        "Shortlisted",
        "Interviewing",
        "Selected",
        "Offered",
        "Accepted",
        "Joined"
    ];

    const index =
        flow.indexOf(status);

    if (
        index === -1 ||
        index >= flow.length - 1
    ) {
        return null;
    }

    return flow[index + 1];
}


// ============================================================
// ADVANCE APPLICATION
// ============================================================

async function advanceApplicationStage(
    applicationId,
    newStatus
) {

    const notes =
        prompt(
            `Move application to ${newStatus}?`,
            "Recruiter reviewed candidate and approved stage transition."
        );

    if (notes === null) {
        return;
    }

    try {

        const res =
            await fetch(
                `/api/applications/${applicationId}/status`,
                {
                    method: "PATCH",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        status: newStatus,
                        notes: notes
                    })
                }
            );

        const data =
            await res.json();

        if (!res.ok) {

            throw new Error(
                data.detail ||
                "Unable to update application."
            );
        }

        alert(
            data.message ||
            `Application moved to ${newStatus}.`
        );

        // Refresh proposal pipeline
        await loadRecruiterApplicationPipeline();

        // Refresh Candidate Twin data
        await loadAllCandidates();

        // Refresh audit trail
        await loadDecisionRecords();

    } catch (error) {

        console.error(
            "Application stage update error:",
            error
        );

        alert(
            error.message ||
            "Unable to update application stage."
        );
    }
}

// Tab Switcher
function switchTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));

    // Find matching button and tab
    const activeBtn = Array.from(document.querySelectorAll(".tab-btn")).find(btn => btn.getAttribute("onclick").includes(tabName));
    if (activeBtn) activeBtn.classList.add("active");

    const targetContent = document.getElementById(`${tabName}-tab`);
    if (targetContent) targetContent.classList.add("active");

    // Load active tab data

    if (tabName === 'recruiter') {
        loadRecruiterApplicationPipeline();
    } else if (tabName === 'governance') {
        loadDecisionRecords();
        loadOverridesLog();
        loadIntegrityAlerts();
        loadConflicts();
        loadOnboardingRegistry();
    } else if (tabName === 'executive') {
        runSimulation();
        loadB2BTenantConfig();
        loadKnowledgeGraph();
    } else if (tabName === 'ingest') {
        loadIntegrations();
        loadIngestionHistory();
    } else if (tabName === 'consultant') {
        loadKPIs();
        loadGamification();
    } else if (tabName === 'interviewer') {
        loadInterviews();
    } else if (tabName === 'kam') {
        loadAllocations();
        loadDuplications();
        loadEconomics();
    }
}

// Fetch B2B Tenant configuration
async function loadB2BTenantConfig() {
    try {
        const res = await fetch("/api/b2b/tenant-config");
        const data = await res.json();

        document.getElementById("b2b-tier").innerText = data.subscription_tier;
        document.getElementById("b2b-jurisdiction").innerText = data.jurisdiction;
        document.getElementById("b2b-seats").innerText = `${data.active_recruiters_count} / ${data.recruiter_seats_limit}`;
        document.getElementById("b2b-tokens").innerText = `${data.current_token_usage_pct}% used`;
        document.getElementById("b2b-status").innerText = data.governance_compliance_status;
    } catch (e) {
        console.error("Error loading B2B config:", e);
    }
}

// Fetch requirements
async function loadAllRequirements() {
    try {
        const res = await fetch("/api/requirements");
        const data = await res.json();

        // Populate stats
        document.getElementById("emp-stat-req").innerText = data.length;
        let totalVacancyCost = 0;
        data.forEach(r => totalVacancyCost += r.vacancy_cost_daily);
        document.getElementById("emp-stat-cost").innerText = `₹${totalVacancyCost.toLocaleString('en-IN')}`;

        // Populate lists
        const listDiv = document.getElementById("employer-req-list");
        const simSelector = document.getElementById("sim-requirement-selector");

        listDiv.innerHTML = "";
        simSelector.innerHTML = "";

        data.forEach((req, idx) => {
            if (idx === 0 && !currentReqId) {
                currentReqId = req.id;
            }

            const item = document.createElement("div");
            item.className = `action-item ${req.id === currentReqId ? 'active-border' : ''}`;
            item.style.cursor = "pointer";
            item.onclick = () => selectRequirement(req.id);

            const badgeClass = req.urgency === 'High' ? 'badge-danger' : (req.urgency === 'Medium' ? 'badge-warning' : 'badge-info');

            item.innerHTML = `
                <div class="action-info">
                    <span class="action-title">${req.business_outcome.substring(0, 50)}...</span>
                    <span class="action-desc">Target Budget: ₹${req.target_compensation.toLocaleString('en-IN')} LPA • Cost of Vacancy: ₹${req.vacancy_cost_daily}/day</span>
                </div>
                <span class="badge ${badgeClass}">${req.urgency}</span>
            `;
            listDiv.appendChild(item);

            // Add to simulation list
            const opt = document.createElement("option");
            opt.value = req.id;
            opt.innerText = req.business_outcome.substring(0, 45) + "...";
            simSelector.appendChild(opt);
        });

        if (currentReqId) {
            loadRequirementDetail(currentReqId);
        }
    } catch (err) {
        console.error("Error loading requirements:", err);
    }
}

// Select Requirement
function selectRequirement(id) {
    currentReqId = id;
    loadAllRequirements();
}

// Fetch requirement details & Predictive/Prescriptive curves
async function loadRequirementDetail(id) {
    try {
        const res = await fetch(`/api/requirements/${id}`);
        const data = await res.json();

        document.getElementById("req-detail-placeholder").style.display = "none";
        const container = document.getElementById("req-detail-container");
        container.style.display = "block";

        document.getElementById("req-detail-outcome").innerText = data.requirement.business_outcome;
        document.getElementById("req-detail-logistics").innerText = `Urgency: ${data.requirement.urgency} | Mode: ${data.requirement.work_mode} | Compensation: ₹${data.requirement.target_compensation.toLocaleString('en-IN')}`;

        // SLA compliance details
        const slaText = document.getElementById("req-detail-sla");
        const slaBadge = document.getElementById("req-detail-sla-badge");
        if (data.sla) {
            slaText.innerText = `SLA Limit: ${data.sla.limit_hours} hours | Elapsed: ${data.sla.elapsed_hours} hours | Status: ${data.sla.status}`;
            if (data.sla.status === "Compliant") {
                slaBadge.className = "badge badge-success";
                slaBadge.innerText = "Compliant";
            } else {
                slaBadge.className = "badge badge-danger";
                slaBadge.innerText = "Breach Warning";
            }
        }

        // Essential Capabilities
        const essContainer = document.getElementById("req-essential-caps");
        essContainer.innerHTML = "";
        data.requirement.essential_capabilities.forEach(cap => {
            essContainer.innerHTML += `<span class="skill-tag"><span class="skill-dot dot-verified"></span> ${cap}</span>`;
        });

        // Alts
        const altContainer = document.getElementById("req-workforce-alts");
        altContainer.innerHTML = "";
        data.requirement.alternatives_considered.forEach(alt => {
            altContainer.innerHTML += `<span class="skill-tag" style="background: rgba(99,102,241,0.08);">${alt}</span>`;
        });

        // Direct Matches
        const dmContainer = document.getElementById("req-direct-matches");
        dmContainer.innerHTML = "";
        if (data.direct_matches && data.direct_matches.length > 0) {
            data.direct_matches.forEach(match => {
                dmContainer.innerHTML += `
                    <div class="action-item" style="cursor: pointer; margin-bottom: 0.5rem;" onclick="inspectCandidate('${match.candidate_id}', '${id}')">
                        <div class="action-info">
                            <span class="action-title">${match.name}</span>
                            <span class="action-desc">Suitability Score: ${(match.score * 100).toFixed(0)}%</span>
                        </div>
                        <span class="badge badge-success">Direct Fit</span>
                    </div>
                `;
            });
        } else {
            dmContainer.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary);">No direct keyword matches in database.</span>`;
        }

        // Hidden matches
        const hmContainer = document.getElementById("req-hidden-matches");
        hmContainer.innerHTML = "";
        if (data.hidden_matches && data.hidden_matches.length > 0) {
            data.hidden_matches.forEach(match => {
                hmContainer.innerHTML += `
                    <div class="action-item" style="cursor: pointer; margin-bottom: 0.5rem;" onclick="inspectCandidate('${match.candidate_id}', '${id}')">
                        <div class="action-info">
                            <span class="action-title">${match.candidate_name}</span>
                            <span class="action-desc">Adjacent: ${match.matching_adjacencies.join(", ")}</span>
                        </div>
                        <span class="badge badge-warning">Graph Sourced</span>
                    </div>
                `;
            });
        } else {
            hmContainer.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary);">No hidden talent discovered.</span>`;
        }

        // LOAD PREDICTIVE TIME TO FILL
        loadPredictiveTimeToFill(id);

        // LOAD PRESCRIPTIVE SOURCING
        loadPrescriptiveSourcing(id);

    } catch (err) {
        console.error("Error loading requirement details:", err);
    }
}

async function loadPredictiveTimeToFill(reqId) {
    try {
        const res = await fetch(`/api/analytics/predictive/${reqId}`);
        const data = await res.json();

        const ctx = document.getElementById("req-time-to-fill-chart").getContext("2d");
        if (timeToFillChart) timeToFillChart.destroy();

        const labels = data.time_to_fill_curve.map(pt => `${pt.day} Days`);
        const probs = data.time_to_fill_curve.map(pt => (pt.probability * 100).toFixed(0));

        timeToFillChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Fill Probability %',
                    data: probs,
                    borderColor: '#a5b4fc',
                    backgroundColor: 'rgba(165,180,252,0.1)',
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2
                }]
            },
            options: {
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', font: { size: 9 } } },
                    y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', font: { size: 9 } } }
                },
                plugins: { legend: { display: false } }
            }
        });
    } catch (e) {
        console.error(e);
    }
}

async function loadPrescriptiveSourcing(reqId) {
    try {
        const res = await fetch(`/api/analytics/prescriptive/${reqId}`);
        const data = await res.json();

        const div = document.getElementById("req-prescriptions");
        div.innerHTML = "";

        data.prescriptions.forEach(p => {
            div.innerHTML += `
                <div style="background: rgba(99,102,241,0.04); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem; font-size: 0.75rem;">
                    <strong style="color: white; display: block; margin-bottom: 0.15rem;">👉 ${p.action}</strong>
                    <div style="color: var(--text-secondary); line-height: 1.3;">Impact: ${p.impact}</div>
                    <div style="color: var(--success); font-size: 0.7rem; margin-top: 0.2rem;">ROI Cycle: ${p.roi_recovery_period}</div>
                </div>
            `;
        });
    } catch (e) {
        console.error(e);
    }
}

// Submit Business Need
async function submitBusinessNeed() {
    const rawInput = document.getElementById("raw-need-input").value.trim();
    if (!rawInput) return;

    try {
        const res = await fetch("/api/business-need", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ employer_id: "emp_1", raw_text: rawInput })
        });
        const data = await res.json();

        // Clear input
        document.getElementById("raw-need-input").value = "";

        // Refresh requirements
        currentReqId = data.requirement_id;
        await loadAllRequirements();

        alert("Sourcing orchestrator triggered! Requirement twin initialized, skills ontology mapped, and candidates matched.");
    } catch (err) {
        console.error("Error submitting business need:", err);
    }
}

// Fetch Candidates
async function loadAllCandidates() {
    try {
        const token = localStorage.getItem("access_token");

        const res = await fetch("/api/candidates", {
            method: "GET",
            headers: {
                "Accept": "application/json",
                "Authorization": "Bearer " + token
            }
        });
        if (res.status === 401 || res.status === 403) {
            console.error("Candidate API authorization failed:", data);
            return;
        }

        if (!res.ok) {
            throw new Error(
                data.detail || "Failed to load candidates"
            );
        }
        const data = await res.json();

        // Recruiter Action Queue Populate
        const queueDiv = document.getElementById("recruiter-action-queue");
        queueDiv.innerHTML = "";

        const simulatedActions = [
            { id: "cand_1", type: "notice", title: "Notice Period Breach Alert", desc: "Siddharth Sharma notice exceeds Apex 45-day threshold.", badge: "Risk", style: "badge-danger" },
            { id: "cand_4", type: "dropout", title: "Counter-Offer Dropout Hazard", desc: "Pooja Hegde has 82% predicted dropout probability.", badge: "Urgent", style: "badge-danger" },
            { id: "cand_2", type: "freshness", title: "Verify Sourced Skills Graph", desc: "Rhea Sen completed python evaluation challenge.", badge: "Verify", style: "badge-info" },
            { id: "cand_3", type: "silver", title: "Silver-Medalist Re-engagement", desc: "Amit Patel was previously shortlisted for backend role.", badge: "Re-engage", style: "badge-warning" }
        ];

        // Only add actions for candidates that still exist in database
        const activeIds = data.map(c => c.id);
        const filteredActions = simulatedActions.filter(act => activeIds.includes(act.id));

        filteredActions.forEach(action => {
            const item = document.createElement("div");
            item.className = "action-item";
            item.style.cursor = "pointer";
            item.onclick = () => inspectCandidate(action.id, currentReqId || 'req_1');
            item.innerHTML = `
                <div class="action-info">
                    <span class="action-title">${action.title}</span>
                    <span class="action-desc">${action.desc}</span>
                </div>
                <span class="badge ${action.style}">${action.badge}</span>
            `;
            queueDiv.appendChild(item);
        });

        // Candidate Tab Dropdown
        const candSelector = document.getElementById("candidate-selector");
        candSelector.innerHTML = '<option value="">Select Candidate...</option>';
        data.forEach(cand => {
            const opt = document.createElement("option");
            opt.value = cand.id;
            opt.innerText = `${cand.name} (${cand.status})`;
            candSelector.appendChild(opt);
        });
    } catch (err) {
        console.error("Error loading candidates:", err);
    }
}

// Inspect candidate from action queue
async function inspectCandidate(candId, reqId) {
    currentCandId = candId;

    // Switch to Recruiter tab
    switchTab('recruiter');

    try {
        const res = await fetch(`/api/candidates/${candId}?req_id=${reqId}`);
        if (!res.ok) {
            document.getElementById("cand-detail-placeholder").style.display = "block";
            document.getElementById("cand-detail-container").style.display = "none";
            return;
        }
        const candidate = await res.json();

        const matchRes = await fetch(`/api/candidates/${candId}/match/${reqId}`);
        const suitability = await matchRes.json();

        const riskRes = await fetch(`/api/joining-risk/${candId}/${reqId}`);
        const risk = await riskRes.json();

        document.getElementById("cand-detail-placeholder").style.display = "none";
        const container = document.getElementById("cand-detail-container");
        container.style.display = "block";

        document.getElementById("cand-detail-name").innerText = candidate.name;
        document.getElementById("cand-detail-headline").innerText = `Email: ${candidate.email} | Phone: ${candidate.phone}`;

        const statusBadge = document.getElementById("cand-detail-status");
        statusBadge.className = `badge ${candidate.status === 'Joined' ? 'badge-success' : 'badge-info'}`;
        statusBadge.innerText = candidate.status;

        const confidenceBadge = document.getElementById("cand-detail-confidence");
        confidenceBadge.innerText = `Data Confidence: ${(candidate.data_confidence * 100).toFixed(0)}%`;

        const trustBadge = document.getElementById("cand-detail-trust");
        const trustPct = (suitability.evidence_score * 100).toFixed(0);
        trustBadge.innerText = `Authentic Trust: ${trustPct}%`;
        if (trustPct >= 80) {
            trustBadge.className = "badge badge-success";
        } else if (trustPct >= 50) {
            trustBadge.className = "badge badge-warning";
        } else {
            trustBadge.className = "badge badge-danger";
        }

        document.getElementById("cand-detail-notice").innerText = `${candidate.notice_period_days} Days`;
        document.getElementById("cand-detail-salary").innerText = `₹${candidate.current_salary.toLocaleString('en-IN')} LPA (Current) • ₹${candidate.expected_salary.toLocaleString('en-IN')} LPA (Expected)`;
        document.getElementById("cand-detail-location").innerText = `${candidate.location} (${candidate.remote_preference} preferred)`;
        document.getElementById("cand-detail-goals").innerText = `"${candidate.career_goals}"`;

        // Behavioral Scores
        const b = candidate.behavioral_profile;
        document.getElementById("cand-behavior-autonomy").style.width = `${b.autonomy * 100}%`;
        document.getElementById("cand-behavior-autonomy-val").innerText = `${(b.autonomy * 100).toFixed(0)}%`;
        document.getElementById("cand-behavior-collab").style.width = `${b.collaboration * 100}%`;
        document.getElementById("cand-behavior-collab-val").innerText = `${(b.collaboration * 100).toFixed(0)}%`;
        document.getElementById("cand-behavior-growth").style.width = `${b.growth_mindset * 100}%`;
        document.getElementById("cand-behavior-growth-val").innerText = `${(b.growth_mindset * 100).toFixed(0)}%`;

        // Technical Questions
        const qContainer = document.getElementById("cand-detail-questions");
        qContainer.innerHTML = "";
        candidate.interview_questions.forEach(q => {
            qContainer.innerHTML += `<li>${q}</li>`;
        });

        // Compensation recommendations
        document.getElementById("cand-detail-offer-val").innerText = `₹${candidate.offer_recommendation.recommended_offer.toLocaleString('en-IN')} LPA`;
        document.getElementById("cand-detail-offer-reason").innerText = candidate.offer_recommendation.explanation;

        // Counter offer simulations
        document.getElementById("cand-detail-counter-val").innerText = `₹${candidate.negotiation_simulation.predicted_counter_offer.toLocaleString('en-IN')} LPA`;
        document.getElementById("cand-detail-ceiling-val").innerText = `₹${candidate.negotiation_simulation.concession_ceiling.toLocaleString('en-IN')} LPA`;

        // Skills Registry list
        const skillsContainer = document.getElementById("cand-detail-skills");
        skillsContainer.innerHTML = "";
        candidate.skills.forEach(skill => {
            const dotClass = skill.type === 'evidence-verified' ? 'dot-verified' : (skill.type === 'inferred' ? 'dot-inferred' : 'dot-declared');
            skillsContainer.innerHTML += `
                <span class="skill-tag">
                    <span class="skill-dot ${dotClass}"></span>
                    ${skill.name} (Proficiency ${skill.proficiency}/5, Recency ${skill.recency_months}m)
                </span>
            `;
        });

        // Match explanation text
        document.getElementById("cand-detail-matching-explanation").innerText = suitability.explanation;

        // Risk assessment panel
        const riskPanel = document.getElementById("cand-detail-joining-risk-panel");
        if (risk && risk.level) {
            riskPanel.style.display = "block";
            const riskBadge = document.getElementById("cand-detail-risk-badge");
            riskBadge.className = `badge ${risk.level === 'High' ? 'badge-danger' : (risk.level === 'Medium' ? 'badge-warning' : 'badge-success')}`;
            riskBadge.innerText = `${risk.level} Dropout Risk`;

            document.getElementById("cand-detail-risk-reasons").innerText = risk.reasons.join(" ");
            document.getElementById("cand-detail-risk-intervention").innerText = risk.recommended_intervention;
        } else {
            riskPanel.style.display = "none";
        }

        // Render Suitability radar chart
        renderSuitabilityRadar(suitability);

        // Render Preboarding Attrition & Prescriptive Interventions
        renderPreboardingAttrition(risk, candidate.notice_period_days);

    } catch (err) {
        console.error("Error inspecting candidate:", err);
    }
}

// Chart rendering
function renderSuitabilityRadar(suit) {
    const ctx = document.getElementById("suitability-radar-chart").getContext("2d");

    if (suitabilityChart) {
        suitabilityChart.destroy();
    }

    suitabilityChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Capability Fit', 'Evidence Verification', 'Active Recency', 'Logistics Fit', 'Retention Prob'],
            datasets: [{
                label: 'Talent Suitability Vector',
                data: [
                    suit.capability_fit * 100,
                    suit.evidence_score * 100,
                    suit.recency_score * 100,
                    suit.logistics_fit * 100,
                    suit.retention_prob * 100
                ],
                backgroundColor: 'rgba(99, 102, 241, 0.2)',
                borderColor: 'rgba(99, 102, 241, 0.8)',
                pointBackgroundColor: 'rgba(99, 102, 241, 1)',
                pointBorderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            scales: {
                r: {
                    angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    pointLabels: { color: '#9ca3af', font: { size: 10 } },
                    ticks: { display: false, max: 100, min: 0, stepSize: 20 },
                    min: 0,
                    max: 100
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderPreboardingAttrition(risk, noticeDays) {
    const ctx = document.getElementById("cand-preboarding-attrition-chart").getContext("2d");
    if (preboardingAttritionChart) preboardingAttritionChart.destroy();

    // Simulate attrition hazard curve over notice period time
    const intervals = [0, Math.floor(noticeDays / 3), Math.floor(noticeDays * 2 / 3), noticeDays];
    const baseRisk = risk.level === 'High' ? 40 : (risk.level === 'Medium' ? 20 : 5);
    const hazardData = intervals.map((day, idx) => Math.min(95, baseRisk + (idx * 15)));

    preboardingAttritionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: intervals.map(d => `Day ${d}`),
            datasets: [{
                label: 'Cumulative Dropout Prob %',
                data: hazardData,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239,68,68,0.1)',
                fill: true,
                borderWidth: 2,
                tension: 0.2
            }]
        },
        options: {
            scales: {
                x: { grid: { display: false }, ticks: { color: '#9ca3af', font: { size: 8 } } },
                y: { min: 0, max: 100, ticks: { color: '#9ca3af', font: { size: 8 } } }
            },
            plugins: { legend: { display: false } }
        }
    });

    // Prescribe recruiter interventions
    const div = document.getElementById("cand-prescriptions");
    div.innerHTML = `
        <div style="background: rgba(239,68,68,0.03); border: 1px solid rgba(239,68,68,0.15); border-radius: 8px; padding: 0.5rem; font-size: 0.72rem; margin-bottom: 0.4rem;">
            <strong>Immediate:</strong> Trigger direct touchpoint call with Hiring Manager (Guards dropout risk).
        </div>
        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem; font-size: 0.72rem;">
            <strong>Preboarding:</strong> Send Apex AI Lab engineering culture deck & blog assets on Day ${intervals[1]}.
        </div>
    `;
}

// Candidate Experience twin loader
async function loadCareerTwin(candId) {
    if (!candId) {
        document.getElementById("career-twin-info").style.display = "none";
        document.getElementById("career-twin-intelligence").style.display = "none";
        return;
    }

    try {
        const res = await fetch(`/api/candidates/${candId}`);
        if (!res.ok) {
            document.getElementById("career-twin-info").style.display = "none";
            document.getElementById("career-twin-intelligence").style.display = "none";
            return;
        }
        const candidate = await res.json();

        document.getElementById("career-twin-info").style.display = "block";
        document.getElementById("career-twin-intelligence").style.display = "block";

        // Hide delete trace box if reloading
        document.getElementById("purge-lineage-output").style.display = "none";

        // Skills
        const skillsContainer = document.getElementById("career-twin-skills");
        skillsContainer.innerHTML = "";
        candidate.skills.forEach(skill => {
            const dotClass = skill.type === 'evidence-verified' ? 'dot-verified' : (skill.type === 'inferred' ? 'dot-inferred' : 'dot-declared');
            skillsContainer.innerHTML += `
                <span class="skill-tag">
                    <span class="skill-dot ${dotClass}"></span>
                    ${skill.name} (Proficiency ${skill.proficiency}/5, Recency ${skill.recency_months}m)
                </span>
            `;
        });

        // Experience
        const expContainer = document.getElementById("career-twin-experience");
        expContainer.innerHTML = "";
        candidate.experience.forEach(exp => {
            expContainer.innerHTML += `
                <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.75rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 0.25rem;">
                        <strong>${exp.role}</strong>
                        <span style="color: var(--text-secondary);">${exp.duration_months} months</span>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--accent-indigo); margin-bottom: 0.4rem;">${exp.company}</div>
                    <p style="font-size: 0.8rem; color: var(--text-secondary);">${exp.description}</p>
                </div>
            `;
        });

        // Insights
        document.getElementById("career-twin-goals-insight").innerText = `"${candidate.name}'s ultimate goal is: ${candidate.career_goals}"`;

        // Set slider
        document.getElementById("career-salary-slider").value = candidate.expected_salary / 100000;
        updateCareerSalaryVal(candidate.expected_salary / 100000);

        // LOAD CANDIDATE PREDICTIVE CAREER PROGRESSION
        loadCandidatePredictiveCareer(candId);

        loadCandidatePrescriptiveLearning(candId);

        // Proposal: Candidate Job Discovery
        loadCandidateJobMarketplace(candId);
    } catch (err) {
        console.error("Error loading career twin:", err);
    }
}

async function loadCandidatePredictiveCareer(candId) {
    try {
        const res = await fetch(`/api/analytics/candidate-predictive/${candId}`);
        const data = await res.json();

        const div = document.getElementById("career-milestones");
        div.innerHTML = `<span style="font-size: 0.7rem; color: var(--text-secondary); display: block; margin-bottom: 0.3rem;">Promotion readiness index: ${data.next_promotion_readiness}</span>`;

        data.career_twin_milestones.forEach(m => {
            div.innerHTML += `
                <div style="display: flex; justify-content: space-between; font-size: 0.72rem; margin-bottom: 0.15rem; border-left: 2px solid var(--accent-indigo); padding-left: 0.4rem;">
                    <div><strong>${m.role}</strong> (${m.salary_band})</div>
                    <div style="color: var(--accent-indigo);">In ${m.predicted_years} years</div>
                </div>
            `;
        });
    } catch (e) {
        console.error(e);
    }
}

async function loadCandidatePrescriptiveLearning(candId) {
    try {
        const res = await fetch(`/api/analytics/candidate-prescriptive/${candId}`);
        const data = await res.json();

        const div = document.getElementById("career-learning-paths");
        div.innerHTML = "";

        data.learning_prescriptions.forEach(p => {
            div.innerHTML += `
                <div style="margin-bottom: 0.3rem; line-height: 1.3;">
                    <div style="color: var(--warning); font-weight: 600;">Gap: ${p.skill_gap} (${p.difficulty} complexity)</div>
                    <div style="color: var(--text-secondary); font-size: 0.7rem;">Course: ${p.recommended_course}</div>
                    <div style="color: var(--success); font-size: 0.65rem;">Expected Compensation Bump: ${p.expected_salary_lift}</div>
                </div>
            `;
        });
    } catch (e) {
        console.error(e);
    }
}

// Update value labels
function updateCareerSalaryVal(val) {
    document.getElementById("career-salary-val").innerText = `${val} LPA`;
}

function updateSimSalaryVal(val) {
    const sign = val >= 0 ? "+" : "";
    document.getElementById("sim-salary-val").innerText = `${sign}${val}%`;
    runSimulation();
}

// Save Prefs
async function saveCareerPreferences() {
    const candId = document.getElementById("candidate-selector").value;
    if (!candId) return;

    const expectedSalary = parseFloat(document.getElementById("career-salary-slider").value) * 100000;
    const discoverable = document.getElementById("career-optin-discover").checked;

    try {
        const res = await fetch(`/api/candidate/${candId}/preferences`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ expected_salary: expectedSalary, consent_status: discoverable })
        });
        const data = await res.json();
        alert("Career Twin Preferences successfully updated & saved to knowledge graph!");
        loadCareerTwin(candId);
    } catch (err) {
        console.error("Error saving career preferences:", err);
    }
}

// Run What-If Simulation
async function runSimulation() {
    const reqId = document.getElementById("sim-requirement-selector").value;
    if (!reqId) return;

    const salaryChange = parseFloat(document.getElementById("sim-salary-slider").value);
    const allowRemote = document.getElementById("sim-remote-toggle").checked;
    const acceptAdjacent = document.getElementById("sim-adjacent-toggle").checked;

    try {
        const res = await fetch("/api/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                requirement_id: reqId,
                salary_change_pct: salaryChange,
                allow_remote: allowRemote,
                accept_adjacent_skills: acceptAdjacent,
                experience_req_change_years: 0.0
            })
        });
        const data = await res.json();

        document.getElementById("sim-pool-size").innerText = data.pool_size;
        document.getElementById("sim-time-to-fill").innerText = `${data.expected_time_to_fill_days} days`;
        document.getElementById("sim-cost-exposure").innerText = `₹${data.estimated_cost_of_vacancy.toLocaleString('en-IN')}`;
        document.getElementById("sim-recommendation-text").innerText = data.recommended_action;

    } catch (err) {
        console.error("Error running simulation:", err);
    }
}

// Load Ingestion integrations list
async function loadIntegrations() {
    try {
        const res = await fetch("/api/integrations");
        const data = await res.json();

        const listDiv = document.getElementById("integration-list");
        listDiv.innerHTML = "";

        data.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "12px";
            card.style.padding = "1rem";
            card.style.display = "flex";
            card.style.justifyContent = "space-between";
            card.style.alignItems = "center";

            const badgeClass = item.status === 'Connected' ? 'badge-success' : 'badge-danger';
            const actionBtn = item.status === 'Connected'
                ? `<button class="btn-primary" style="font-size: 0.75rem; padding: 0.4rem 0.8rem;" onclick="syncConnector('${item.id}')">Sync Now</button>`
                : `<button class="btn-secondary" style="font-size: 0.75rem; padding: 0.4rem 0.8rem; cursor: not-allowed;" disabled>Connect</button>`;

            card.innerHTML = `
                <div>
                    <h4 style="font-family: var(--font-heading); font-size: 0.95rem; margin-bottom: 0.25rem;">${item.name}</h4>
                    <span style="font-size: 0.75rem; color: var(--text-secondary);">Frequency: ${item.sync_frequency} | Last Run: ${item.last_sync.substring(11, 19)}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span class="badge ${badgeClass}">${item.status}</span>
                    ${actionBtn}
                </div>
            `;
            listDiv.appendChild(card);
        });
    } catch (err) {
        console.error("Error loading integrations:", err);
    }
}

// Sync external API trigger
async function syncConnector(connectorId) {
    try {
        const res = await fetch(`/api/integrations/${connectorId}/sync?candidate_id=cand_1`, {
            method: "POST"
        });
        const data = await res.json();

        alert(`Successfully synchronized ${data.name}! Trust score upgraded to ${(data.new_confidence * 100).toFixed(0)}%. Updated skills: ${data.updated_skills.join(", ")}`);

        loadIngestionHistory();
        loadIntegrations();
        loadAllCandidates();
    } catch (err) {
        console.error("Error triggering sync:", err);
    }
}

// Upload resume text file mock
async function uploadResumeText() {
    const text = document.getElementById("resume-paste-text").value.trim();
    if (!text) return;

    try {
        const res = await fetch("/api/ingest/resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ raw_text: text })
        });
        const data = await res.json();

        document.getElementById("resume-paste-text").value = "";
        alert(`Resume parsed successfully by Ingestion Agent! Created candidate: ${data.name}`);

        loadIngestionHistory();
        loadAllCandidates();
    } catch (err) {
        console.error("Error uploading resume:", err);
    }
}

// Load Ingestion Logs
async function loadIngestionHistory() {
    try {
        const res = await fetch("/api/ingest/history");
        const data = await res.json();

        const listDiv = document.getElementById("ingest-history-list");
        listDiv.innerHTML = "";

        data.forEach(log => {
            const item = document.createElement("div");
            item.style.background = "rgba(0,0,0,0.2)";
            item.style.border = "1px solid var(--border-color)";
            item.style.borderRadius = "8px";
            item.style.padding = "0.75rem";
            item.style.fontSize = "0.8rem";

            item.innerHTML = `
                <div style="display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 0.25rem;">
                    <span style="color: var(--accent-indigo);">📂 ${log.source}</span>
                    <span style="color: var(--text-secondary); font-size: 0.75rem;">${log.timestamp.substring(11, 19)}</span>
                </div>
                <p style="color: var(--text-primary); line-height: 1.4;">${log.details}</p>
                <div style="margin-top: 0.4rem; text-align: right;">
                    <span class="badge badge-success">${log.status}</span>
                </div>
            `;
            listDiv.appendChild(item);
        });
    } catch (err) {
        console.error("Error loading ingestion logs:", err);
    }
}

// Load KPIs Grid
async function loadKPIs() {
    try {
        const res = await fetch("/api/kpis");
        const data = await res.json();

        const container = document.getElementById("kpi-grid-container");
        container.innerHTML = "";

        data.forEach(kpi => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "12px";
            card.style.padding = "1rem";

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase;">${kpi.role} KPI</span>
                    <span class="badge badge-info" style="font-size: 0.65rem;">Active Tracking</span>
                </div>
                <h4 style="font-family: var(--font-heading); font-size: 0.95rem; margin-bottom: 0.25rem;">${kpi.kpi_name}</h4>
                <p style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.75rem; line-height: 1.3;">${kpi.kra_desc}</p>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; border-top: 1px solid var(--border-color); padding-top: 0.5rem;">
                    <div>Current: <strong style="color: var(--accent-indigo);">${kpi.current_value}</strong></div>
                    <div>Target: <strong style="color: var(--success);">${kpi.target_value}</strong></div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error("Error loading KPIs:", err);
    }
}

// Load Leaderboard
async function loadGamification() {
    try {
        const res = await fetch("/api/consultants/gamification");
        const data = await res.json();

        const container = document.getElementById("gamification-leaderboard");
        container.innerHTML = "";

        data.forEach((item, idx) => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "12px";
            card.style.padding = "1rem";
            card.style.display = "flex";
            card.style.justifyContent = "space-between";
            card.style.alignItems = "center";

            const badgesList = item.badges.map(b => `<span class="badge badge-warning" style="font-size: 0.65rem; margin-right: 0.25rem;">🏆 ${b}</span>`).join("");

            card.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <div style="width: 1.8rem; height: 1.8rem; background: rgba(99,102,241,0.2); color: var(--accent-indigo); font-weight: 700; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.9rem;">
                        ${idx + 1}
                    </div>
                    <div>
                        <h4 style="font-family: var(--font-heading); font-size: 0.95rem; margin-bottom: 0.25rem;">${item.consultant_name}</h4>
                        <div style="margin-top: 0.25rem; display: flex; flex-wrap: wrap; gap: 0.25rem;">
                            ${badgesList}
                        </div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <h3 style="font-size: 1.2rem; color: var(--accent-blue); font-family: var(--font-heading);">${item.points.toLocaleString()} pts</h3>
                    <span style="font-size: 0.7rem; color: var(--text-secondary); text-transform: uppercase;">${item.level}</span>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error("Error loading gamification dashboard:", err);
    }
}

// Fetch Agent Decisions
async function loadDecisionRecords() {

    const stream =
        document.getElementById("decision-log-stream");

    if (!stream) {
        return;
    }

    try {

        const res =
            await fetch("/api/decisions");

        if (!res.ok) {

            console.warn(
                "Decision API unavailable:",
                res.status
            );

            stream.innerHTML = `
                <div style="
                    color:var(--text-secondary);
                    font-size:0.75rem;
                    padding:0.75rem;
                ">
                    Decision records are available
                    to authorized users.
                </div>
            `;

            return;
        }

        const data =
            await res.json();

        if (!Array.isArray(data)) {

            console.warn(
                "Unexpected decision API response:",
                data
            );

            return;
        }

        stream.innerHTML = "";

        data.forEach(dec => {

            const entry =
                document.createElement("div");

            entry.className =
                "log-entry";

            entry.innerHTML = `
                <div class="log-header">
                    <span>
                        ⚙️ ${dec.agent_name}
                    </span>

                    <span>
                        ${new Date(
                dec.timestamp
            ).toLocaleTimeString()}
                    </span>
                </div>

                <div style="
                    margin-bottom:0.4rem;
                    font-weight:600;
                ">
                    Objective:
                    ${dec.objective}
                </div>

                <div style="
                    margin-bottom:0.4rem;
                    color:var(--text-secondary);
                ">
                    Rules Applied:
                    ${dec.rules_applied}
                </div>

                <div style="
                    margin-bottom:0.4rem;
                    color:var(--text-secondary);
                ">
                    Evidence Considered:
                    ${dec.evidence_considered}
                </div>

                <div>
                    Recommendation:
                    ${dec.recommendation}
                </div>
            `;

            stream.appendChild(entry);

        });

    } catch (error) {

        console.error(
            "Error loading decisions:",
            error
        );

    }
}

// MCP Play interface execution
async function runMCPTool() {
    const tool = document.getElementById("mcp-tool-select").value;
    const argsText = document.getElementById("mcp-args-input").value;

    let args = {};
    try {
        args = JSON.parse(argsText);
    } catch (e) {
        alert("Invalid JSON format in Tool Arguments!");
        return;
    }

    try {
        const res = await fetch("/mcp/tools/call", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: tool, arguments: args })
        });
        const data = await res.json();

        document.getElementById("mcp-output-container").style.display = "block";
        document.getElementById("mcp-output").innerText = JSON.stringify(data, null, 2);
    } catch (err) {
        console.error("Error calling MCP tool:", err);
    }
}

// Recruiter interactions
function triggerDecline() {
    alert("System restriction: Autonomous employment rejection prohibited without explicit human signoff. Action logged to policy engine.");
}

function triggerEngagement() {
    alert("Candidate Twin Engaged. Sourcing orchestration email/calendar invites auto-scheduled based on Candidate notice constraints.");
}

// --- SME & INTERVIEWER BINDINGS ---

async function loadInterviews() {
    try {
        const res = await fetch("/api/interviews");
        const data = await res.json();

        const listDiv = document.getElementById("interviewer-assign-list");
        listDiv.innerHTML = "";

        data.forEach(item => {
            const el = document.createElement("div");
            el.className = `action-item ${item.id === currentInterviewId ? 'active-border' : ''}`;
            el.style.cursor = "pointer";

            const skillsStr = JSON.stringify(item.candidate_skills);
            el.onclick = () => selectInterview(item.id, item.candidate_name, item.business_outcome, skillsStr);

            const badgeClass = item.status === 'Completed' ? 'badge-success' : 'badge-warning';
            el.innerHTML = `
                <div class="action-info">
                    <span class="action-title">${item.candidate_name} &bull; Technical Eval</span>
                    <span class="action-desc">JD: ${item.business_outcome.substring(0, 45)}...</span>
                    <span class="action-desc">Time: ${item.scheduled_time.substring(11, 16)} &bull; SME: ${item.interviewer_name}</span>
                </div>
                <span class="badge ${badgeClass}">${item.status}</span>
            `;
            listDiv.appendChild(el);
        });
    } catch (e) {
        console.error(e);
    }
}

async function selectInterview(id, candidateName, outcome, skillsStr) {
    currentInterviewId = id;

    loadInterviews();

    document.getElementById("interviewer-eval-placeholder").style.display = "none";
    document.getElementById("interviewer-eval-container").style.display = "block";

    document.getElementById("eval-cand-name").innerText = `${candidateName} - Technical Evaluation`;
    document.getElementById("eval-req-outcome").innerText = `Hiring Need: "${outcome}"`;

    const skills = JSON.parse(skillsStr);
    const cbContainer = document.getElementById("eval-skills-checkboxes");
    cbContainer.innerHTML = "";
    skills.forEach(s => {
        const checked = s.type === 'evidence-verified' ? 'checked disabled' : '';
        cbContainer.innerHTML += `
            <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                <input type="checkbox" name="verify-skill-check" value="${s.name}" ${checked} style="width: 1.1rem; height: 1.1rem; accent-color: var(--accent-indigo);">
                <span>${s.name} <span style="font-size: 0.75rem; color: var(--text-secondary);">(${s.type})</span></span>
            </label>
        `;
    });

    try {
        const candidateDetailsRes = await fetch(`/api/candidates/${currentCandId || 'cand_1'}?req_id=req_1`);
        const cand = await candidateDetailsRes.json();

        const qList = document.getElementById("eval-agent-questions");
        qList.innerHTML = "";
        cand.interview_questions.forEach(q => {
            qList.innerHTML += `<li>${q}</li>`;
        });
    } catch (e) {
        console.error("Error loading interview questions:", e);
    }
}

async function submitInterviewFeedback() {
    if (!currentInterviewId) return;

    const checkboxes = document.querySelectorAll('input[name="verify-skill-check"]:checked');
    const skills = Array.from(checkboxes).map(cb => cb.value);
    const score = parseInt(document.getElementById("eval-score-select").value);
    const notes = document.getElementById("eval-notes-input").value.trim();

    try {
        const res = await fetch(`/api/interviews/${currentInterviewId}/feedback`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                score: score,
                notes: notes,
                skills_to_verify: skills
            })
        });
        const data = await res.json();
        alert("Evaluation feedback submitted. Verification engine completed successfully. Trust rating updated.");

        document.getElementById("eval-notes-input").value = "";
        document.getElementById("interviewer-eval-container").style.display = "none";
        document.getElementById("interviewer-eval-placeholder").style.display = "block";

        loadInterviews();
        loadDecisionRecords();
        loadAllCandidates();
    } catch (e) {
        console.error(e);
    }
}

// --- AI KAM & PAYOUT BINDINGS ---

async function loadDuplications() {
    try {
        const res = await fetch("/api/kam/duplications");
        const data = await res.json();

        const list = document.getElementById("kam-duplicate-list");
        list.innerHTML = "";

        if (data.length === 0) {
            list.innerHTML = `<span style="font-size: 0.85rem; color: var(--text-secondary);">No duplicate candidate submissions conflicts pending.</span>`;
            return;
        }

        data.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "12px";
            card.style.padding = "1rem";
            card.style.display = "flex";
            card.style.flexDirection = "column";
            card.style.gap = "0.5rem";

            let actionHtml = "";
            if (item.resolved_status === 'Pending') {
                actionHtml = `
                    <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                        <button class="btn-primary" style="font-size: 0.75rem; padding: 0.4rem 0.8rem;" onclick="resolveDuplicate('${item.id}', '${item.consultant_1_id}')">Favor ${item.consultant_1_name}</button>
                        <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.4rem 0.8rem;" onclick="resolveDuplicate('${item.id}', '${item.consultant_2_id}')">Favor ${item.consultant_2_name}</button>
                    </div>
                `;
            } else {
                const winner = item.resolved_status === 'Resolved_1' ? item.consultant_1_name : item.consultant_2_name;
                actionHtml = `
                    <div style="margin-top: 0.25rem;"><span class="badge badge-success">Dispute Resolved favoring ${winner}</span></div>
                `;
            }

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <strong style="font-size: 1rem; color: white;">Dispute: ${item.candidate_name}</strong>
                    <span class="badge badge-danger">Duplication Collision</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                    <div>1. Submitted by <strong>${item.consultant_1_name}</strong> at ${item.submitted_at_1.substring(11, 19)}</div>
                    <div>2. Submitted by <strong>${item.consultant_2_name}</strong> at ${item.submitted_at_2.substring(11, 19)}</div>
                </div>
                ${actionHtml}
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
    }
}

async function resolveDuplicate(id, favConsultantId) {
    try {
        const res = await fetch(`/api/kam/duplications/${id}/resolve?favoring_consultant_id=${favConsultantId}`, {
            method: "POST"
        });
        const data = await res.json();
        alert(data.message);
        loadDuplications();
        loadDecisionRecords();
    } catch (e) {
        console.error(e);
    }
}

async function loadAllocations() {
    try {
        const res = await fetch("/api/kam/allocations");
        const data = await res.json();

        const list = document.getElementById("kam-allocations-list");
        list.innerHTML = "";

        data.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "8px";
            card.style.padding = "0.75rem";
            card.style.fontSize = "0.8rem";

            card.innerHTML = `
                <div style="font-weight: 600; color: var(--accent-indigo); margin-bottom: 0.25rem;">${item.consultant_name}</div>
                <div style="color: var(--text-secondary); font-size: 0.75rem;">Allocated to: "${item.business_outcome.substring(0, 45)}..."</div>
                <div style="margin-top: 0.4rem; text-align: right;">
                    <span class="badge badge-success">${item.status} Allocation</span>
                </div>
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
    }
}

async function loadEconomics() {
    try {
        const res = await fetch("/api/kam/economics");
        const data = await res.json();

        const list = document.getElementById("kam-economics-list");
        list.innerHTML = "";

        data.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "12px";
            card.style.padding = "1rem";

            card.innerHTML = `
                <div style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase;">JD: ${item.business_outcome.substring(0, 35)}...</div>
                <h4 style="font-family: var(--font-heading); font-size: 1rem; color: white; margin-top: 0.25rem; margin-bottom: 0.75rem;">Economics Twin Pipeline Calculator</h4>
                
                <div style="font-size: 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; justify-content: space-between;">
                        <span>Expected Placement Commission (15%):</span>
                        <strong>₹${item.placement_revenue.toLocaleString('en-IN')}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>Operational Delivery Cost:</span>
                        <strong style="color: var(--text-secondary);">₹${item.delivery_cost.toLocaleString('en-IN')}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>Notice Period Vacancy Risk (30d):</span>
                        <strong style="color: var(--danger);">₹${item.risk_cost.toLocaleString('en-IN')}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>Sourcing Probability of Fill:</span>
                        <strong>${(item.fill_probability * 100).toFixed(0)}%</strong>
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-color); padding-top: 0.75rem;">
                    <span style="font-size: 0.85rem; font-weight: 600;">Expected Pipeline Value:</span>
                    <strong style="font-size: 1.25rem; color: var(--success); font-family: var(--font-heading);">₹${item.expected_value.toLocaleString('en-IN')}</strong>
                </div>
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
    }
}

// --- GRC & INTEGRITY BINDINGS ---

async function loadOverridesLog() {
    try {
        const res = await fetch("/api/overrides");
        const data = await res.json();

        const list = document.getElementById("overrides-log-list");
        list.innerHTML = "";

        if (data.length === 0) {
            list.innerHTML = `<span style="font-size: 0.8rem; color: var(--text-secondary);">No policy overrides applied.</span>`;
            return;
        }

        data.forEach(item => {
            const row = document.createElement("div");
            row.style.background = "rgba(0,0,0,0.2)";
            row.style.border = "1px solid var(--border-color)";
            row.style.borderRadius = "8px";
            row.style.padding = "0.5rem";
            row.style.fontSize = "0.75rem";

            row.innerHTML = `
                <div style="display: flex; justify-content: space-between; font-weight: 600; color: var(--warning); margin-bottom: 0.25rem;">
                    <span>🛡️ Override: ${item.id}</span>
                    <span>${item.timestamp.substring(11, 19)}</span>
                </div>
                <div style="line-height: 1.3;">Reason: "${item.reason}"</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 0.25rem;">
                    Decision Target: ${item.original_decision_id} &bull; Actor: ${item.overridden_by} &bull; Auth: ${item.approver} &bull; Conflict Declared: ${item.conflict_declaration ? 'YES' : 'NO'}
                </div>
            `;
            list.appendChild(row);
        });
    } catch (e) {
        console.error("Error loading overrides:", e);
    }
}

async function submitOverride() {
    const decId = document.getElementById("over-decision-id").value.trim();
    const approver = document.getElementById("over-approver").value.trim();
    const reason = document.getElementById("over-reason").value.trim();
    const conflict = document.getElementById("over-conflict").checked;

    if (!decId || !approver || !reason) {
        alert("Please specify Decision ID, Approver Name and Reason!");
        return;
    }

    try {
        const res = await fetch("/api/overrides", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                original_decision_id: decId,
                overridden_by: "HR_System_Admin",
                reason: reason,
                approver: approver,
                conflict_declaration: conflict
            })
        });
        const data = await res.json();
        alert(data.message);

        // Reset override fields
        document.getElementById("over-decision-id").value = "";
        document.getElementById("over-approver").value = "";
        document.getElementById("over-reason").value = "";
        document.getElementById("over-conflict").checked = false;

        loadOverridesLog();
        loadDecisionRecords();
    } catch (e) {
        console.error(e);
    }
}

async function loadIntegrityAlerts() {
    try {
        const res = await fetch("/api/integrity/alerts");
        const data = await res.json();

        const list = document.getElementById("integrity-alerts-list");
        list.innerHTML = "";

        if (data.length === 0) {
            list.innerHTML = `<span style="font-size: 0.8rem; color: var(--text-secondary);">No active integrity exceptions reported.</span>`;
            return;
        }

        data.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "12px";
            card.style.padding = "0.75rem";

            const badgeClass = item.severity === 'High' ? 'badge-danger' : 'badge-warning';
            let actionHtml = "";
            if (item.status === 'Pending') {
                actionHtml = `
                    <div style="display: flex; gap: 0.4rem; margin-top: 0.5rem; justify-content: flex-end;">
                        <button class="btn-primary" style="font-size: 0.7rem; padding: 0.3rem 0.6rem;" onclick="triageAlert('${item.id}', 'Under Investigation')">Investigate</button>
                        <button class="btn-secondary" style="font-size: 0.7rem; padding: 0.3rem 0.6rem;" onclick="triageAlert('${item.id}', 'Dismissed')">Dismiss</button>
                    </div>
                `;
            } else {
                actionHtml = `
                    <div style="margin-top: 0.4rem; text-align: right;"><span class="badge badge-success">${item.status}</span></div>
                `;
            }

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                    <strong style="font-size: 0.85rem; color: white;">Anomaly: ${item.category}</strong>
                    <span class="badge ${badgeClass}">${item.severity} Risk</span>
                </div>
                <p style="font-size: 0.75rem; color: var(--text-secondary); line-height: 1.4;">${item.description}</p>
                <div style="font-size: 0.65rem; color: var(--text-secondary); margin-top: 0.25rem;">Detected: ${item.timestamp.substring(11, 19)}</div>
                ${actionHtml}
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
    }
}

async function triageAlert(id, newStatus) {
    const notes = prompt(`Enter triage action notes for Alert ${id}:`, "Processed anomaly via compliance workspace.");
    if (notes === null) return; // Cancelled

    try {
        const res = await fetch(`/api/integrity/alerts/${id}/triage`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                new_status: newStatus,
                triage_notes: notes
            })
        });
        const data = await res.json();
        alert(data.message);
        loadIntegrityAlerts();
        loadDecisionRecords();
    } catch (e) {
        console.error(e);
    }
}

async function loadConflicts() {
    try {
        const res = await fetch("/api/integrity/conflicts");
        const data = await res.json();

        const list = document.getElementById("conflicts-registry-list");
        list.innerHTML = "";

        data.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(0,0,0,0.2)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "8px";
            card.style.padding = "0.5rem";
            card.style.fontSize = "0.75rem";

            card.innerHTML = `
                <div style="font-weight: 600; color: var(--accent-indigo); margin-bottom: 0.15rem;">
                    Relation: ${item.relationship_type} (${item.severity} Severity)
                </div>
                <div>Parties: <strong>${item.party_1}</strong> &bull; <strong>${item.party_2}</strong></div>
                <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 0.2rem; line-height: 1.3;">
                    Mitigation: "${item.mitigation_plan}"
                </div>
                <div style="margin-top: 0.3rem; text-align: right;">
                    <span class="badge badge-success">${item.declared_status}</span>
                </div>
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error(e);
    }
}

async function submitConflict() {
    const p1 = document.getElementById("coi-p1").value.trim();
    const p2 = document.getElementById("coi-p2").value.trim();
    const rel = document.getElementById("coi-rel").value.trim();
    const mitigation = document.getElementById("coi-mitigation").value.trim();

    if (!p1 || !p2 || !rel || !mitigation) {
        alert("Please complete all fields to declare conflict!");
        return;
    }

    try {
        const res = await fetch("/api/integrity/conflicts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                party_1: p1,
                party_2: p2,
                relationship_type: rel,
                mitigation_plan: mitigation,
                severity: "Medium"
            })
        });
        const data = await res.json();
        alert(data.message);

        // Reset COI fields
        document.getElementById("coi-p1").value = "";
        document.getElementById("coi-p2").value = "";
        document.getElementById("coi-rel").value = "";
        document.getElementById("coi-mitigation").value = "";

        loadConflicts();
        loadDecisionRecords();
    } catch (e) {
        console.error(e);
    }
}

async function requestCandidatePurge() {
    const candId = document.getElementById("candidate-selector").value;
    if (!candId) {
        alert("Please select a Career Twin persona first.");
        return;
    }

    const check = confirm("WARNING: Executing a full data deletion will wipe your Candidate Twin, experience registry, assessment scores, and interviews from all operational stores and graph nodes. This action is auditable and irreversible. Proceed?");
    if (!check) return;

    try {
        const res = await fetch(`/api/candidates/${candId}/delete-request`, {
            method: "POST"
        });
        const data = await res.json();

        const box = document.getElementById("purge-lineage-output");
        box.style.display = "block";
        box.innerHTML = `
            <div><strong>Wiped Candidate:</strong> ${data.candidate_name} (${data.candidate_id})</div>
            <div><strong>Data minimised status:</strong> ${data.status}</div>
            <div><strong>Trace path lineage search:</strong> ${data.tables_traced.join(", ")}</div>
            <div><strong>Total twin records wiped:</strong> ${data.records_deleted}</div>
            <div><strong>Governance:</strong> ${data.governance_log}</div>
        `;

        alert("GDPR / DPDP Deletion completed. All operational registers purged successfully.");

        // Refresh candidate lists
        loadAllCandidates();
        loadDecisionRecords();
    } catch (e) {
        console.error(e);
    }
}

// --- NEW STAKEHOLDER ONBOARDING HANDLERS ---

function toggleOnboardingFields(role) {
    document.getElementById("onb-field-candidate").style.display = role === "Candidate" ? "block" : "none";
    document.getElementById("onb-field-interviewer").style.display = role === "Interviewer" ? "block" : "none";
    document.getElementById("onb-field-employer").style.display = role === "Employer" ? "block" : "none";
}

async function loadOnboardingRegistry() {
    try {
        const res = await fetch("/api/onboarding");
        const data = await res.json();

        const list = document.getElementById("onboarding-registry-list");
        list.innerHTML = "";

        data.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.01)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "8px";
            card.style.padding = "0.6rem";
            card.style.fontSize = "0.75rem";

            const skillsList = item.capabilities_registered.map(s => `<span class="badge badge-info" style="font-size:0.6rem; margin-right:0.2rem;">${s}</span>`).join("");
            const assessmentDetails = Object.entries(item.structural_assessment).map(([k, v]) => `<div>${k.replace('_', ' ')}: <strong>${v}</strong></div>`).join("");

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.2rem; font-weight: 600;">
                    <span>👤 ${item.stakeholder_name} (${item.role})</span>
                    <span class="badge ${item.completion_status === 'Completed' ? 'badge-success' : 'badge-warning'}">${item.completion_status}</span>
                </div>
                <div style="margin-bottom: 0.3rem;">Skills: ${skillsList || 'None'}</div>
                <div style="font-size: 0.7rem; color: var(--text-secondary); line-height: 1.3;">
                    ${assessmentDetails}
                    <div>Consent Boundary: <strong>${item.compliance_optin ? 'Opted-In' : 'No'}</strong></div>
                </div>
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error("Error loading onboarding registry:", e);
    }
}

async function submitOnboardingForm() {
    const name = document.getElementById("onb-name").value.trim();
    const role = document.getElementById("onb-role").value;
    const skillsRaw = document.getElementById("onb-skills").value.trim();
    const consent = document.getElementById("onb-consent").checked;

    if (!name) {
        alert("Please enter a stakeholder name.");
        return;
    }

    const skills = skillsRaw ? skillsRaw.split(",").map(s => s.trim()) : [];

    let structural = {};
    if (role === "Candidate") {
        structural.career_direction = document.getElementById("onb-career").value.trim() || "MLOps/Backend Architect Engineering.";
    } else if (role === "Interviewer") {
        structural.interviewer_tier = document.getElementById("onb-interviewer-tier").value;
    } else if (role === "Employer") {
        structural.org_growth_rate = document.getElementById("onb-growth").value.trim() || "Rapid Scaling";
    }

    try {
        const res = await fetch("/api/onboarding", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                stakeholder_name: name,
                role: role,
                step_progress: 4,
                capabilities_registered: skills,
                structural_assessment: structural,
                compliance_optin: consent
            })
        });

        const data = await res.json();
        alert(data.message);

        loadOnboardingRegistry();
        loadAllCandidates();
        loadInterviews();
        loadDecisionRecords();
    } catch (e) {
        console.error("Error submitting onboarding:", e);
    }
}

// --- NEW RAG & KNOWLEDGE GRAPH HANDLERS ---

async function runRAGSearch() {
    const query = document.getElementById("rag-search-query").value.trim();
    if (!query) return;

    try {
        const res = await fetch(`/api/rag/search?query=${encodeURIComponent(query)}`);
        const data = await res.json();

        const container = document.getElementById("rag-search-results");
        container.innerHTML = "";

        if (data.results.length === 0) {
            container.innerHTML = `<span style="font-size: 0.75rem; color: var(--text-secondary);">No semantic matches found.</span>`;
            return;
        }

        data.results.forEach(item => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.02)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "8px";
            card.style.padding = "0.5rem";
            card.style.fontSize = "0.72rem";
            card.style.cursor = "pointer";
            card.onclick = () => inspectCandidate(item.candidate_id, currentReqId || 'req_1');

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.2rem; font-weight: 600;">
                    <strong>👤 ${item.name}</strong>
                    <span style="color: var(--accent-indigo);">${(item.similarity_score * 100).toFixed(0)}% Sim</span>
                </div>
                <div style="color: var(--text-secondary); line-height: 1.3; font-style: italic;">
                    "${item.matched_chunks[0].substring(0, 110)}..."
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Error running RAG Search:", e);
    }
}

async function loadKnowledgeGraph() {
    try {
        const res = await fetch("/api/graph/nodes");
        const data = await res.json();

        const container = document.getElementById("kg-network-list");
        container.innerHTML = "";

        data.nodes.forEach(n => {
            const card = document.createElement("div");
            card.style.background = "rgba(255,255,255,0.01)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "8px";
            card.style.padding = "0.5rem";
            card.style.fontSize = "0.75rem";

            let color = "var(--text-secondary)";
            if (n.group === "Skill") color = "var(--accent-blue)";
            else if (n.group === "Candidate") color = "#c084fc";
            else if (n.group === "Organization" || n.group === "Employer") color = "var(--success)";

            const conns = data.links.filter(l => l.source === n.id || l.target === n.id);
            const connsList = conns.map(l => {
                const partner = l.source === n.id ? l.target : l.source;
                return `${partner} (${(l.weight * 100).toFixed(0)}%)`;
            }).join(", ");

            card.innerHTML = `
                <div style="font-weight: 600; color: ${color}; margin-bottom: 0.25rem;">● ${n.id} (${n.group})</div>
                <div style="color: var(--text-secondary); font-size: 0.68rem; line-height:1.3;">
                    Connected: ${connsList || 'None'}
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Error loading knowledge graph:", e);
    }
}
// ============================================================
// LEVELUPWARDS PROPOSAL
// CANDIDATE JOB DISCOVERY + AI MATCHING
// ============================================================

async function loadCandidateJobMarketplace(candId) {

    if (!candId) {
        return;
    }

    const careerTwin = document.getElementById("career-twin-intelligence");

    if (!careerTwin) {
        console.warn("Career Twin intelligence container not found.");
        return;
    }

    // Prevent duplicate marketplace sections
    let marketplace = document.getElementById("candidate-job-marketplace");

    if (!marketplace) {

        marketplace = document.createElement("div");

        marketplace.id = "candidate-job-marketplace";

        marketplace.style.marginTop = "1.5rem";
        marketplace.style.padding = "1rem";
        marketplace.style.border = "1px solid var(--border-color)";
        marketplace.style.borderRadius = "14px";
        marketplace.style.background = "rgba(255,255,255,0.02)";

        careerTwin.appendChild(marketplace);
    }

    marketplace.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; gap:1rem; flex-wrap:wrap;">

            <div>
                <div style="
                    font-size:0.7rem;
                    color:var(--accent-indigo);
                    font-weight:700;
                    text-transform:uppercase;
                    letter-spacing:0.08em;
                ">
                    AI Talent Marketplace
                </div>

                <h3 style="
                    margin:0.2rem 0 0;
                    font-family:var(--font-heading);
                    font-size:1.15rem;
                    color:white;
                ">
                    Recommended Opportunities
                </h3>

                <p style="
                    margin:0.25rem 0 0;
                    font-size:0.75rem;
                    color:var(--text-secondary);
                ">
                    Requirement Twins matched against your Career Twin.
                </p>
            </div>

            <span id="candidate-job-count"
                  class="badge badge-info">
                Loading...
            </span>

        </div>

        <div id="candidate-job-loading"
             style="
                padding:2rem;
                text-align:center;
                color:var(--text-secondary);
                font-size:0.8rem;
             ">
            Loading AI-matched opportunities...
        </div>

        <div id="candidate-job-list"
             style="
                display:grid;
                grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
                gap:1rem;
             ">
        </div>
    `;

    try {

        const res = await fetch("/api/jobs");

        if (!res.ok) {

            if (res.status === 401) {
                marketplace.innerHTML = `
                    <div style="
                        padding:1.5rem;
                        text-align:center;
                        color:var(--text-secondary);
                    ">
                        Please sign in to discover opportunities.
                    </div>
                `;
                return;
            }

            throw new Error(`Job discovery failed: ${res.status}`);
        }

        const data = await res.json();

        const jobs = data.jobs || [];

        document.getElementById("candidate-job-loading").style.display = "none";

        document.getElementById("candidate-job-count").innerText =
            `${jobs.length} Opportunities`;

        const list = document.getElementById("candidate-job-list");

        list.innerHTML = "";

        if (jobs.length === 0) {

            list.innerHTML = `
                <div style="
                    grid-column:1/-1;
                    padding:2rem;
                    text-align:center;
                    color:var(--text-secondary);
                    border:1px dashed var(--border-color);
                    border-radius:10px;
                ">
                    No active opportunities are currently available.
                </div>
            `;

            return;
        }

        /*
         * ------------------------------------------------------
         * Calculate suitability for every job
         * ------------------------------------------------------
         */

        const scoredJobs = [];

        for (const job of jobs) {

            try {

                const matchRes = await fetch(
                    `/api/candidates/${candId}/match/${job.requirement_id}`
                );

                if (matchRes.ok) {

                    const suitability = await matchRes.json();

                    scoredJobs.push({
                        job: job,
                        suitability: suitability
                    });

                } else {

                    scoredJobs.push({
                        job: job,
                        suitability: null
                    });
                }

            } catch (error) {

                console.error(
                    "Suitability calculation failed:",
                    job.requirement_id,
                    error
                );

                scoredJobs.push({
                    job: job,
                    suitability: null
                });
            }
        }

        /*
         * Highest AI suitability first
         */

        scoredJobs.sort((a, b) => {

            const scoreA =
                a.suitability?.overall_suitability || 0;

            const scoreB =
                b.suitability?.overall_suitability || 0;

            return scoreB - scoreA;
        });

        /*
         * Render job cards
         */

        scoredJobs.forEach(item => {

            const job = item.job;
            const suitability = item.suitability;

            const score =
                suitability?.overall_suitability || 0;

            const scorePercent =
                Math.round(score * 100);

            const role = job.role || {};

            const title =
                role.title ||
                job.business_outcome ||
                "Open Opportunity";

            const description =
                role.generated_jd ||
                job.business_outcome ||
                "Opportunity details available.";

            const skills =
                job.essential_capabilities || [];

            const application =
                job.application || {};

            const alreadyApplied =
                application.applied === true;

            let scoreClass = "badge-danger";

            if (scorePercent >= 80) {
                scoreClass = "badge-success";
            } else if (scorePercent >= 60) {
                scoreClass = "badge-warning";
            }

            const card =
                document.createElement("div");

            card.style.border =
                "1px solid var(--border-color)";

            card.style.borderRadius =
                "12px";

            card.style.padding =
                "1rem";

            card.style.background =
                "rgba(255,255,255,0.025)";

            card.style.display =
                "flex";

            card.style.flexDirection =
                "column";

            card.style.gap =
                "0.7rem";

            const skillHTML =
                skills.slice(0, 5).map(skill => `
                    <span class="skill-tag"
                          style="font-size:0.65rem;">
                        ${escapeJobHTML(skill)}
                    </span>
                `).join("");

            const applyButton = alreadyApplied
                ? `
                    <button
                        class="btn-secondary"
                        disabled
                        style="
                            width:100%;
                            font-size:0.75rem;
                            opacity:0.8;
                        ">
                        ✓ Applied
                    </button>
                  `
                : `
                    <button
                        class="btn-primary"
                        style="
                            width:100%;
                            font-size:0.75rem;
                        "
                        onclick="openCandidateJob(
                            '${job.requirement_id}',
                            '${escapeJobAttribute(title)}',
                            '${escapeJobAttribute(description)}'
                        )">
                        View Opportunity
                    </button>
                  `;

            card.innerHTML = `

                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:flex-start;
                    gap:0.5rem;
                ">

                    <div>

                        <div style="
                            font-size:0.65rem;
                            color:var(--text-secondary);
                            text-transform:uppercase;
                            margin-bottom:0.25rem;
                        ">
                            ${escapeJobHTML(job.urgency || "Open")} Priority
                        </div>

                        <h4 style="
                            margin:0;
                            font-family:var(--font-heading);
                            font-size:0.95rem;
                            color:white;
                        ">
                            ${escapeJobHTML(title)}
                        </h4>

                    </div>

                    <span class="badge ${scoreClass}">
                        ${scorePercent}% Match
                    </span>

                </div>

                <p style="
                    margin:0;
                    font-size:0.72rem;
                    line-height:1.5;
                    color:var(--text-secondary);
                ">
                    ${escapeJobHTML(
                description.substring(0, 180)
            )}
                    ${description.length > 180 ? "..." : ""}
                </p>

                <div style="
                    display:flex;
                    flex-wrap:wrap;
                    gap:0.3rem;
                ">
                    ${skillHTML}
                </div>

                <div style="
                    display:grid;
                    grid-template-columns:1fr 1fr;
                    gap:0.5rem;
                    font-size:0.7rem;
                ">

                    <div style="
                        padding:0.5rem;
                        background:rgba(255,255,255,0.03);
                        border-radius:7px;
                    ">
                        <span style="color:var(--text-secondary);">
                            Compensation
                        </span>

                        <strong style="
                            display:block;
                            color:white;
                            margin-top:0.15rem;
                        ">
                            ₹${Number(
                job.target_compensation || 0
            ).toLocaleString("en-IN")}
                        </strong>
                    </div>

                    <div style="
                        padding:0.5rem;
                        background:rgba(255,255,255,0.03);
                        border-radius:7px;
                    ">
                        <span style="color:var(--text-secondary);">
                            Work Mode
                        </span>

                        <strong style="
                            display:block;
                            color:white;
                            margin-top:0.15rem;
                        ">
                            ${escapeJobHTML(
                job.work_mode || "Not specified"
            )}
                        </strong>
                    </div>

                </div>

                ${suitability
                    ? `
                        <div style="
                            border-top:1px solid var(--border-color);
                            padding-top:0.6rem;
                            font-size:0.68rem;
                        ">

                            <div style="
                                display:flex;
                                justify-content:space-between;
                                margin-bottom:0.25rem;
                            ">
                                <span style="color:var(--text-secondary);">
                                    Capability Fit
                                </span>

                                <strong>
                                    ${Math.round(
                        suitability.capability_fit * 100
                    )}%
                                </strong>
                            </div>

                            <div style="
                                height:4px;
                                background:rgba(255,255,255,0.08);
                                border-radius:5px;
                                overflow:hidden;
                            ">
                                <div style="
                                    width:${Math.round(
                        suitability.capability_fit * 100
                    )}%;
                                    height:100%;
                                    background:var(--accent-indigo);
                                "></div>
                            </div>

                        </div>
                    `
                    : ""
                }

                ${applyButton}
            `;

            list.appendChild(card);
        });

    } catch (error) {

        console.error(
            "Candidate job marketplace error:",
            error
        );

        const loading =
            document.getElementById(
                "candidate-job-loading"
            );

        if (loading) {

            loading.innerHTML = `
                <div style="
                    color:var(--danger);
                    margin-bottom:0.4rem;
                ">
                    Unable to load opportunities.
                </div>

                <button
                    class="btn-secondary"
                    onclick="loadCandidateJobMarketplace('${candId}')"
                    style="font-size:0.7rem;">
                    Try Again
                </button>
            `;
        }
    }
}


// ============================================================
// JOB DETAIL + APPLY
// ============================================================

async function openCandidateJob(
    requirementId,
    title,
    description
) {

    const existing =
        document.getElementById(
            "candidate-job-detail-modal"
        );

    if (existing) {
        existing.remove();
    }

    const modal =
        document.createElement("div");

    modal.id =
        "candidate-job-detail-modal";

    modal.style.position = "fixed";
    modal.style.inset = "0";
    modal.style.background = "rgba(0,0,0,0.65)";
    modal.style.zIndex = "9999";
    modal.style.display = "flex";
    modal.style.alignItems = "center";
    modal.style.justifyContent = "center";
    modal.style.padding = "1rem";

    modal.innerHTML = `

        <div style="
            width:min(700px,100%);
            max-height:90vh;
            overflow:auto;
            background:#111827;
            border:1px solid var(--border-color);
            border-radius:16px;
            padding:1.25rem;
        ">

            <div style="
                display:flex;
                justify-content:space-between;
                gap:1rem;
                align-items:flex-start;
            ">

                <div>

                    <span class="badge badge-info">
                        Requirement Twin
                    </span>

                    <h2 style="
                        color:white;
                        font-family:var(--font-heading);
                        margin:0.6rem 0 0.3rem;
                        font-size:1.3rem;
                    ">
                        ${escapeJobHTML(title)}
                    </h2>

                </div>

                <button
                    class="btn-secondary"
                    onclick="closeCandidateJobModal()">
                    ✕
                </button>

            </div>

            <div style="
                margin-top:1rem;
                color:var(--text-secondary);
                font-size:0.8rem;
                line-height:1.7;
                white-space:pre-wrap;
            ">
                ${escapeJobHTML(description)}
            </div>

            <div style="
                margin-top:1rem;
                padding:0.8rem;
                border:1px solid var(--border-color);
                border-radius:10px;
                background:rgba(255,255,255,0.02);
            ">

                <div style="
                    font-size:0.7rem;
                    color:var(--text-secondary);
                    margin-bottom:0.4rem;
                ">
                    APPLICATION NOTE
                </div>

                <textarea
                    id="candidate-cover-note"
                    rows="4"
                    placeholder="Tell the employer why this opportunity fits your career goals..."
                    style="
                        width:100%;
                        resize:vertical;
                        background:rgba(0,0,0,0.2);
                        border:1px solid var(--border-color);
                        border-radius:8px;
                        padding:0.7rem;
                        color:white;
                        font-size:0.75rem;
                    "
                ></textarea>

            </div>

            <div style="
                display:flex;
                justify-content:flex-end;
                gap:0.5rem;
                margin-top:1rem;
            ">

                <button
                    class="btn-secondary"
                    onclick="closeCandidateJobModal()">
                    Cancel
                </button>

                <button
                    id="candidate-apply-button"
                    class="btn-primary"
                    onclick="applyToCandidateJob('${requirementId}')">
                    Apply Now
                </button>

            </div>

        </div>
    `;

    document.body.appendChild(modal);
}


function closeCandidateJobModal() {

    const modal =
        document.getElementById(
            "candidate-job-detail-modal"
        );

    if (modal) {
        modal.remove();
    }
}


// ============================================================
// APPLY TO JOB
// ============================================================

async function applyToCandidateJob(requirementId) {

    const candidateId =
        document.getElementById(
            "candidate-selector"
        )?.value;

    if (!candidateId) {

        alert(
            "Please select your Candidate Twin before applying."
        );

        return;
    }

    const note =
        document.getElementById(
            "candidate-cover-note"
        )?.value.trim() || "";

    const button =
        document.getElementById(
            "candidate-apply-button"
        );

    if (button) {

        button.disabled = true;
        button.innerText = "Submitting...";
    }

    try {

        const res =
            await fetch(
                `/api/requirements/${requirementId}/apply`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        cover_note: note || null
                    })
                }
            );

        const data =
            await res.json();

        if (!res.ok) {

            throw new Error(
                data.detail ||
                "Unable to submit application."
            );
        }

        const match =
            data.matching || {};

        const score =
            Math.round(
                (match.overall_suitability || 0) * 100
            );

        closeCandidateJobModal();

        alert(
            `Application submitted successfully.\n\n` +
            `AI Suitability: ${score}%\n\n` +
            `${match.explanation || ""}`
        );

        // Refresh candidate state
        await loadAllCandidates();

        await loadCareerTwin(candidateId);

        await loadCandidateJobMarketplace(candidateId);

    } catch (error) {

        console.error(
            "Application submission error:",
            error
        );

        if (button) {

            button.disabled = false;
            button.innerText = "Apply Now";
        }

        alert(
            error.message ||
            "Unable to submit application."
        );
    }
}


// ============================================================
// SAFE HTML HELPERS
// ============================================================

function escapeJobHTML(value) {

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function escapeJobAttribute(value) {

    return String(value ?? "")
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'");
}