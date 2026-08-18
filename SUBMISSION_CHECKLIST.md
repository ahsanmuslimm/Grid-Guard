# GridGuard — Submission Checklist
**Deadline: June 11, 2026 2:00 PM PT**

---

## Phase 07 — Secret Manager ✅ / ⬜

- [ ] `PHOENIX_API_KEY` stored: `gcloud secrets describe PHOENIX_API_KEY`
- [ ] `NVD_API_KEY` stored: `gcloud secrets describe NVD_API_KEY`
- [ ] Both secrets confirmed: `gcloud secrets list`
- [ ] No hardcoded keys in codebase: `grep -r "phx_" . --include="*.py"`

---

## Phase 09 — Cloud Run ✅ / ⬜

- [ ] Deployed: `gcloud run services list`
- [ ] URL saved: `https://gridguard-xxxx-uc.a.run.app`
- [ ] Dashboard loads from **external** device/network
- [ ] Health check returns 200: `curl https://YOUR_URL/health`
- [ ] min-instances=1 set (no cold starts): visible in Cloud Run console
- [ ] Full attack cycle completes in <90s on public URL
- [ ] Phoenix traces appear for Cloud Run runs (not just local)
- [ ] Secrets injected correctly in production (no ⚠ PHOENIX_API_KEY warnings in logs)

---

## Phase 10 — Demo Video ✅ / ⬜

- [ ] Rehearsed demo script minimum **5 times**
- [ ] Screen recording software tested
- [ ] All 4 attack scenarios tested on live URL before recording
- [ ] Recording is exactly **under 3:00** (Devpost rules)
- [ ] Video shows: inject → detect → investigate → approve → resolve → Phoenix traces
- [ ] Hallucination flag **visible and pointed to** in Phoenix
- [ ] Response quality score visible
- [ ] Auto-generated incident report shown
- [ ] GitHub URL and live URL shown at end
- [ ] Uploaded to YouTube as **Public** (not unlisted)
- [ ] YouTube URL saved

---

## GitHub Repo ✅ / ⬜

- [ ] Repo is **Public** (not private)
- [ ] `LICENSE` file present (Apache 2.0)
- [ ] Apache 2.0 shows in **About** section of GitHub repo
- [ ] `README.md` complete with:
  - [ ] Architecture diagram (text or image)
  - [ ] Setup instructions (works on first try)
  - [ ] Demo video link (YouTube URL)
  - [ ] Live URL
  - [ ] Team members listed
- [ ] No `.env` committed: `git log --all -- .env`
- [ ] No `credentials/` committed: `git log --all -- credentials/`
- [ ] All source files present and importable

---

## Devpost Submission ✅ / ⬜

- [ ] Account created at devpost.com
- [ ] Hackathon found and project created
- [ ] **Arize track selected** (not just Google Cloud track)
- [ ] All team members added to Devpost project
- [ ] Hosted URL field filled: `https://gridguard-xxxx-uc.a.run.app`
- [ ] GitHub repo URL filled
- [ ] Demo video URL filled (YouTube)
- [ ] Description covers:
  - [ ] What GridGuard does (1-2 sentences)
  - [ ] Key features (bullet list)
  - [ ] Technologies used (ADK, Gemini, Phoenix, Cloud Run, MITRE, NVD)
  - [ ] Data sources (MITRE ATT&CK ICS, NVD CVE API, SCADA simulator)
  - [ ] What was learned / challenges
- [ ] Submitted **before June 11 2:00 PM PT**

---

## Final Verification Commands

Run these in order the hour before submission:

```bash
# 1. Confirm project structure
python verify_pipeline.py

# 2. Confirm Cloud Run is live
curl https://YOUR_CLOUD_RUN_URL/health

# 3. Confirm full attack cycle on public URL
curl -X POST https://YOUR_CLOUD_RUN_URL/api/inject-attack/ransomware

# 4. Confirm no credentials in git
git log --all --full-diff -p -- .env credentials/

# 5. Confirm repo is public
# (check GitHub repo page — no "Private" badge)

# 6. Confirm video is public on YouTube
# (open incognito window, paste YouTube URL)
```

---

## Emergency Contacts

If Cloud Run fails during demo:
1. `gcloud run logs read --service gridguard --region us-central1 --limit 50`
2. Redeploy: `bash deploy/deploy_cloudrun.sh`
3. If cold start: confirm `--min-instances=1` is set

If Phoenix not showing traces:
1. Check `PHOENIX_API_KEY` is in Secret Manager
2. Check Cloud Run logs for "PHOENIX_API_KEY not set" warning
3. Verify project name is exactly `gridguard` (case-sensitive)

---

**One sentence that defines winning:**
> When the Arize judge opens Phoenix after the demo and sees every decision traced, a hallucination flagged, and a quality score attached — that's the moment GridGuard separates from every other team.
