# GridGuard — 3-Minute Demo Script
**Rehearse this 5 times minimum before recording.**

---

## Pre-Demo Checklist (do before hitting record)

- [ ] Cloud Run URL open in browser — dashboard loads, 12 green nodes
- [ ] Arize Phoenix dashboard open in second tab
- [ ] Microphone checked — voice clear
- [ ] Screen recording software running (1080p minimum)
- [ ] Phone/tablet ready on separate network for external test
- [ ] All 4 attack buttons tested — responses working
- [ ] No cold start — Cloud Run min-instances=1 confirmed


---

## Exact Script (3:00 total)

### 0:00 – 0:20 | IMPACT HOOK

> *Show 3 statistics on screen or slide — talk over them:*

**SAY:**
"Energy infrastructure is the most attacked critical sector on the planet.
Weekly cyberattacks on utilities have increased 4x since 2020.
Today's AI-powered attackers move faster than any human operator can respond.

The AI defending these grids can't be trusted or explained.
**GridGuard fixes both.**"

**SHOW:** Stats slide or the GridGuard dashboard loading

---

### 0:20 – 0:40 | LIVE DEMO STARTS

> *Switch to live dashboard at your Cloud Run URL*

**SAY:**
"This is GridGuard running live on Google Cloud Run.
12 energy grid nodes — all green, all nominal.
Watch what happens when I inject a ransomware attack."

**DO:** Click the **🔒 Ransomware** button

**SHOW:** Node turns red within 3 seconds. Agent Decision Timeline starts populating.

---

### 0:40 – 1:10 | AGENT PIPELINE LIVE

> *Stay on dashboard, point to timeline events as they appear*

**SAY:**
"The GridGuard agent is now running autonomously.
It's reading SCADA telemetry — voltage drop detected, dangerous commands found.

It's querying MITRE ATT&CK for ICS — technique T0803 matched.
It's querying the NIST National Vulnerability Database — real CVE IDs returned.

It's classifying this as **CRITICAL** — because ransomware commands were confirmed."

**SHOW:** Timeline showing `detection_agent` → `investigation_agent` steps with tool call results

---

### 1:10 – 1:30 | HUMAN APPROVAL GATE

> *The approval modal appears automatically*

**SAY:**
"Because this is a CRITICAL threat, GridGuard has paused and surfaced the full AI reasoning for operator review.

The operator sees exactly what the agent found, why it classified it CRITICAL,
which MITRE techniques matched, which CVEs are relevant,
and what response it wants to execute.

The countdown is running. I'll click **Approve**."

**DO:** Click **✓ Approve Response**

**SAY:**
"The agent executes the ransomware playbook — isolates the node, blocks the C2 IP, alerts the SOC."

**SHOW:** Timeline shows `response_agent` executing actions, node changes to blue (resolved)

---

### 1:30 – 2:20 | ARIZE PHOENIX — THE DIFFERENTIATOR

> *Switch to Arize Phoenix tab*

**SAY:**
"Now here's what makes GridGuard unique.

Every single decision the agent just made is fully traced in Arize Phoenix.
Here's the complete span tree for this incident."

**SHOW:** Phoenix trace tree — each span: `scada.read_telemetry`, `detection.voltage_anomaly_check`, `investigation.mitre_lookup`, `investigation.cve_lookup`, `gridguard.full_pipeline`

**SAY:**
"Every span has the exact input, output, latency, and confidence score.

And here — watch this — the hallucination evaluator.
When the agent tried to reference a CVE it couldn't verify against the actual NVD data,
Phoenix flagged it."

**SHOW:** Hallucination flag on a span — point to it

**SAY:**
"This is the trust layer that no other system provides.
You don't just know *what* the AI did — you know *why*, and whether you can trust it."

**SHOW:** The actual response quality score produced for this incident (do not use a hard-coded value).

---

### 2:20 – 2:45 | SECOND SCENARIO + INCIDENT REPORT

> *Back to dashboard*

**SAY:**
"One more — let me inject a DDoS attack.
This is HIGH severity, so no human approval required — the agent responds automatically."

**DO:** Click **💥 DDoS Attack** button

**SAY:**
"Different attack type, different playbook — rate limiting, BGP blackholing, NOC alert.
And after resolution, GridGuard auto-generates a plain-English incident report."

**DO:** Click the incident report that appears

**SHOW:** Report modal — executive summary, what happened, MITRE techniques, CVEs, actions taken

---

### 2:45 – 3:00 | IMPACT CLOSE

> *Show GitHub repo or dashboard one last time*

**SAY:**
"GridGuard works on any energy grid, globally.
Open source, Apache 2.0 license.
Deployable in under an hour on Google Cloud.

At near-zero infrastructure cost compared to $500K enterprise solutions.

The code is at **github.com/YOUR_USERNAME/gridguard**.
The live system is running right now."

**SHOW:** GitHub repo + live URL

---

## Critical Timing Notes

| Timestamp | Must-see moment |
|-----------|----------------|
| 0:23 | Node turns red on attack inject |
| 0:45 | Timeline shows first agent tool call |
| 1:12 | Approval modal appears |
| 1:18 | Operator clicks Approve |
| 1:35 | Phoenix trace tree visible |
| 1:50 | **Hallucination flag highlighted** ← judges remember this |
| 2:00 | Quality score shown |
| 2:22 | DDoS auto-response (no approval) |
| 2:35 | Incident report open |

---

## Common Mistakes to Avoid

- ❌ Don't talk over the approval modal appearing — pause and let judges see it
- ❌ Don't skip the hallucination flag — this is your knockout moment with Arize judges
- ❌ Don't let the demo window sit idle — keep narrating while pipeline runs
- ❌ Don't go over 3:00 — Devpost rules say only first 3 minutes are evaluated
- ✅ Do keep browser zoomed in on Phoenix spans — they need to be readable on video
- ✅ Do have a backup recording ready in case Cloud Run hiccups
