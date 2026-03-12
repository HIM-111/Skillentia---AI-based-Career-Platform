document.addEventListener('DOMContentLoaded', function() {
    if (!requireAuth('auth.html')) {
        return;
    }
    verifyAuth().then((isValid) => {
        if (!isValid) {
            window.location.href = 'auth.html';
        }
    });
    bindLogoutButtons();

    const refreshButton = document.getElementById('refresh-dashboard-btn');
    const missingContext = document.getElementById('dashboard-missing-context');
    const currentScore = document.getElementById('dashboard-current-score');
    const updatedScore = document.getElementById('dashboard-updated-score');
    const scoreDelta = document.getElementById('dashboard-score-delta');
    const recommendations = document.getElementById('dashboard-recommendations');
    const missingSkills = document.getElementById('dashboard-missing-skills');
    const developmentPlan = document.getElementById('dashboard-development-plan');
    const priorityTable = document.getElementById('dashboard-priority-table');
    const topJobsContainer = document.getElementById('dashboard-top-jobs');
    const jobsUpdated = document.getElementById('dashboard-jobs-updated');
    const lastUpdated = document.getElementById('dashboard-last-updated');
    const downloadCoverLetterBtn = document.getElementById('download-cover-letter-btn');
    const downloadUpdatedResumeBtn = document.getElementById('download-updated-resume-btn');

    let latestCoverLetter = '';
    let latestUpdatedResume = '';
    const FEATURE_RESULT_CACHE_KEY = 'careerPlatformFeatureResults';
    const FEATURE_RESULT_CACHE_VERSION = 'v2';

    function normalizeText(value) {
        return String(value || '')
            .replace(/\r\n/g, '\n')
            .replace(/[ \t]+/g, ' ')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    }

    function simpleHash(input) {
        let hash = 0;
        const text = String(input || '');
        for (let i = 0; i < text.length; i += 1) {
            hash = ((hash << 5) - hash) + text.charCodeAt(i);
            hash |= 0;
        }
        return String(hash);
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function sanitizeUrl(url) {
        const value = String(url || '').trim();
        if (!value) {
            return '#';
        }
        if (/^https?:\/\//i.test(value)) {
            return value;
        }
        return '#';
    }

    function getCachedJobResults(resumeText, jobDescription) {
        const user = (typeof getAuthUser === 'function' ? getAuthUser() : {}) || {};
        const userId = user.id ? String(user.id) : 'anonymous';
        const contextHash = simpleHash(
            `${FEATURE_RESULT_CACHE_VERSION}\n${String(resumeText || '').trim()}\n---\n${String(jobDescription || '').trim()}`
        );

        try {
            const store = JSON.parse(localStorage.getItem(FEATURE_RESULT_CACHE_KEY) || '{}');
            const entry = (((store[userId] || {}).jobs) || null);
            if (!entry || entry.context_hash !== contextHash) {
                return null;
            }
            return {
                payload: entry.payload || null,
                updatedAt: entry.updated_at || ''
            };
        } catch (_error) {
            return null;
        }
    }

    function normalizePlanStep(step) {
        if (step && typeof step === 'object') {
            const skill = String(step.skill || '').trim();
            const action = String(step.action || step.step || '').trim();
            if (skill && action) {
                return `${skill}: ${action}`;
            }
            if (action) {
                return action;
            }
            if (skill) {
                return `Develop ${skill}`;
            }
            return '';
        }

        const text = normalizeText(step);
        if (!text) {
            return '';
        }
        const skillMatch = text.match(/['"]skill['"]\s*:\s*['"]([^'"]+)['"]/i);
        const actionMatch = text.match(/['"]action['"]\s*:\s*['"]([^'"]+)['"]/i);
        if (skillMatch && actionMatch) {
            return `${skillMatch[1].trim()}: ${actionMatch[1].trim()}`;
        }
        return text;
    }

    function asPercent(value) {
        return Number.isFinite(value) ? `${value}%` : '--';
    }

    function applyDelta(delta) {
        scoreDelta.classList.remove('score-positive', 'score-negative');
        if (!Number.isFinite(delta)) {
            scoreDelta.textContent = '--';
            return;
        }
        scoreDelta.textContent = `${delta >= 0 ? '+' : ''}${delta}%`;
        scoreDelta.classList.add(delta >= 0 ? 'score-positive' : 'score-negative');
    }

    function renderSkills(skills) {
        if (!skills.length) {
            missingSkills.innerHTML = '<span class="insight-subtitle">No major skill gaps detected.</span>';
            return;
        }
        missingSkills.innerHTML = skills.map((skill) => (
            `<span class="skill-tag skill-missing">${skill}</span>`
        )).join('');
    }

    function renderPlan(items) {
        const normalized = (items || [])
            .map((item) => normalizePlanStep(item))
            .filter(Boolean);

        if (!normalized.length) {
            developmentPlan.innerHTML = '<li>No action items available.</li>';
            return;
        }
        developmentPlan.innerHTML = normalized.map((item) => `<li>${item}</li>`).join('');
    }

    function renderPriorityRows(rows) {
        if (!rows.length) {
            priorityTable.innerHTML = '<tr><td colspan="3">No priority gaps available.</td></tr>';
            return;
        }
        priorityTable.innerHTML = rows.slice(0, 8).map((item) => (
            `<tr>
                <td>${item.skill || ''}</td>
                <td><span class="priority-badge priority-${String(item.priority || 'Medium').toLowerCase()}">${item.priority || 'Medium'}</span></td>
                <td>${Number.isFinite(item.mention_count) ? item.mention_count : 0}</td>
            </tr>`
        )).join('');
    }

    function renderTopJobs(jobsInput, updatedAt) {
        if (!topJobsContainer) {
            return;
        }
        const jobs = Array.isArray(jobsInput) ? jobsInput.slice(0, 3) : [];

        if (jobsUpdated) {
            const ts = updatedAt ? new Date(updatedAt) : null;
            jobsUpdated.textContent = (ts && !Number.isNaN(ts.getTime()))
                ? `Last job listings update: ${ts.toLocaleString()}`
                : (jobs.length ? 'Last job listings update: Not available' : '');
        }

        if (!jobs.length) {
            topJobsContainer.innerHTML = '<div class="job-empty">No cached job listings for the current context. Run Job Listings once to populate this section.</div>';
            return;
        }

        topJobsContainer.innerHTML = jobs.map((job) => {
            const safeUrl = sanitizeUrl(job.url || '');
            const score = Number.isFinite(job.compatibility_score) ? `${job.compatibility_score}% match` : 'Matched listing';
            return `
                <article class="dashboard-job-item">
                    <div class="dashboard-job-head">
                        <h4 class="dashboard-job-title">${escapeHtml(job.title || 'Job listing')}</h4>
                        <span class="job-score">${escapeHtml(score)}</span>
                    </div>
                    <div class="job-meta">${escapeHtml(job.company || 'Unknown company')} • ${escapeHtml(job.location || 'Not specified')}</div>
                    <a class="job-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">Open Listing</a>
                </article>
            `;
        }).join('');
    }

    async function loadDashboard() {
        showLoading('Loading reports...');
        try {
            const [data, context] = await Promise.all([
                APIService.getDashboard(),
                APIService.getUserContext()
            ]);
            latestCoverLetter = data.cover_letter || '';
            latestUpdatedResume = data.updated_resume || '';
            const serverJobs = Array.isArray(data.top_job_listings) ? data.top_job_listings : [];
            const serverJobsUpdatedAt = String(data.job_listings_updated_at || '').trim();
            if (serverJobs.length) {
                renderTopJobs(serverJobs, serverJobsUpdatedAt);
            } else {
                const cachedJobs = getCachedJobResults(context.resume_text || '', context.job_description || '');
                const cachedJobsPayload = (cachedJobs || {}).payload || {};
                renderTopJobs(cachedJobsPayload.jobs || [], (cachedJobs || {}).updatedAt || '');
            }

            if (!data.has_context) {
                missingContext.style.display = 'block';
            } else {
                missingContext.style.display = 'none';
            }

            currentScore.textContent = asPercent(data.resume_ats_score);
            updatedScore.textContent = asPercent(data.updated_resume_ats_score);

            const delta = (
                Number.isFinite(data.resume_ats_score) &&
                Number.isFinite(data.updated_resume_ats_score)
            ) ? (data.updated_resume_ats_score - data.resume_ats_score) : null;
            applyDelta(delta);

            recommendations.textContent = data.recommendations || 'Run skills gap analysis to generate targeted recommendations.';
            recommendations.textContent = normalizeText(
                data.recommendations || 'Run skills gap analysis to generate targeted recommendations.'
            );
            renderSkills(data.skills_to_develop || []);
            renderPlan(data.development_plan || []);
            renderPriorityRows(data.prioritized_gaps || []);

            if (data.artifact_updated_at) {
                const ts = new Date(data.artifact_updated_at);
                lastUpdated.textContent = Number.isNaN(ts.getTime())
                    ? ''
                    : `Last artifact update: ${ts.toLocaleString()}`;
            } else {
                lastUpdated.textContent = '';
            }

            downloadCoverLetterBtn.disabled = !latestCoverLetter.trim();
            downloadUpdatedResumeBtn.disabled = !latestUpdatedResume.trim();
        } catch (error) {
            showToast(error.message || 'Failed to load reports', 'error');
        } finally {
            hideLoading();
        }
    }

    downloadCoverLetterBtn.addEventListener('click', function() {
        if (!latestCoverLetter.trim()) {
            showToast('No generated cover letter available yet', 'warning');
            return;
        }
        const cleanedCoverLetter = (typeof sanitizeCoverLetterText === 'function')
            ? sanitizeCoverLetterText(latestCoverLetter)
            : latestCoverLetter;
        downloadGeneratedPdf(cleanedCoverLetter, 'cover-letter.pdf', '');
    });

    downloadUpdatedResumeBtn.addEventListener('click', function() {
        if (!latestUpdatedResume.trim()) {
            showToast('No updated resume available yet', 'warning');
            return;
        }
        downloadGeneratedPdf(latestUpdatedResume, 'updated-resume.pdf', '');
    });

    refreshButton.addEventListener('click', loadDashboard);
    loadDashboard();
});
