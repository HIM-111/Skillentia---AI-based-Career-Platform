// UI Helper Functions

/**
 * Show loading overlay
 */
function showLoading(message = 'Processing...') {
    const overlay = document.getElementById('loading-overlay');
    const loadingText = overlay.querySelector('.loading-text');
    if (loadingText) {
        loadingText.textContent = message;
    }
    overlay.classList.add('active');
}

/**
 * Hide loading overlay
 */
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.remove('active');
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    }[type] || 'ℹ️';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Remove after 5 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function sanitizeUrl(url) {
    try {
        const parsed = new URL(url);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
            return parsed.toString();
        }
    } catch (error) {
        return '#';
    }
    return '#';
}

const RESUME_SECTION_HEADERS = new Set([
    'SUMMARY',
    'PROFILE',
    'SKILLS',
    'SOFT SKILLS',
    'EXPERIENCE',
    'PROJECTS',
    'EDUCATION',
    'LANGUAGES',
    'REFERENCES',
    'CERTIFICATIONS',
    'AWARDS',
    'PUBLICATIONS',
    'VOLUNTEER',
    'ACTIVITIES',
    'LEADERSHIP',
    'CONTACT',
    'INTERESTS',
    'OTHER'
]);

function isResumeSectionHeading(line) {
    const normalized = String(line || '').trim().replace(/[:\-]+$/, '').toUpperCase();
    return RESUME_SECTION_HEADERS.has(normalized);
}

function isUnderlineLine(line) {
    return /^[-_=~.]{3,}$/.test(String(line || '').trim());
}

function isProjectTitleLine(line) {
    const text = String(line || '').trim().replace(/^[•\-\u2013\u2014]\s*/, '');
    if (!text || text.endsWith('.') || text.includes(':')) {
        return false;
    }
    const words = text.split(/\s+/).filter(Boolean);
    if (words.length < 2 || words.length > 12) {
        return false;
    }
    const lower = text.toLowerCase();
    if (/\b(was|were|is|are|built|developed|implemented|created|designed|using|required|helped|allow|allowed)\b/.test(lower)) {
        return false;
    }
    if (/^(the|an|a)\s+/.test(lower) && words.length > 5) {
        return false;
    }
    const titleRatio = words.filter((word) => /^[A-Z]/.test(word)).length / words.length;
    return titleRatio >= 0.55;
}

function isProjectTitleContinuation(line) {
    const text = String(line || '').trim();
    if (!text || /[.!?]$/.test(text)) {
        return false;
    }
    const words = text.split(/\s+/).filter(Boolean);
    if (words.length > 4) {
        return false;
    }
    if (/\)$/.test(text) || /^\(/.test(text)) {
        return true;
    }
    const titleRatio = words.filter((word) => /^[A-Z]/.test(word)).length / Math.max(1, words.length);
    return /^[A-Z]/.test(text) && titleRatio >= 0.7;
}

function isProjectEntryLine(line) {
    const text = String(line || '').trim();
    const match = text.match(/^([A-Z][A-Za-z0-9()&+/'\-\s]{2,80}):\s*(.+)$/);
    if (!match) {
        return false;
    }
    const title = match[1].trim();
    const description = match[2].trim();
    return Boolean(title && description && title.split(/\s+/).length <= 14);
}

function explodeProjectEntries(lines) {
    const titleRegex = /([A-Z][A-Za-z0-9()&+/'\-\s]{2,80}):\s*/g;
    const result = [];

    (lines || []).forEach((rawLine) => {
        const text = String(rawLine || '').trim();
        if (!text) {
            return;
        }
        const matches = [...text.matchAll(titleRegex)];
        if (matches.length <= 1) {
            result.push(text);
            return;
        }

        for (let idx = 0; idx < matches.length; idx += 1) {
            const start = matches[idx].index;
            const end = (idx + 1 < matches.length) ? matches[idx + 1].index : text.length;
            const chunk = text.slice(start, end).replace(/\s+/g, ' ').trim();
            if (chunk) {
                result.push(chunk);
            }
        }
    });

    return result;
}

function splitSentenceJoinedProjects(lines) {
    const boundary = /(?<=\.)\s+(?=[A-Z][A-Za-z0-9()&+/'\-\s]{2,80}:\s*)/g;
    const output = [];
    (lines || []).forEach((rawLine) => {
        const text = String(rawLine || '').trim();
        if (!text) {
            return;
        }
        const parts = text.split(boundary).map((part) => part.replace(/\s+/g, ' ').trim()).filter(Boolean);
        if (parts.length) {
            output.push(...parts);
        } else {
            output.push(text);
        }
    });
    return output;
}

function formatProjectLines(lines) {
    const normalized = splitSentenceJoinedProjects(explodeProjectEntries((lines || [])
        .map((line) => String(line || '').trim().replace(/^[•\-\u2013\u2014]\s*/, ''))
        .filter(Boolean)));

    if (!normalized.length) {
        return [];
    }

    const out = [];
    let title = '';
    let desc = [];

    const flush = () => {
        if (title && desc.length) {
            out.push(`${title}: ${desc.join(' ').trim()}`);
        } else if (title) {
            out.push(title);
        } else if (desc.length) {
            out.push(desc.join(' ').trim());
        }
        title = '';
        desc = [];
    };

    normalized.forEach((line) => {
        if (isProjectEntryLine(line)) {
            flush();
            out.push(line);
        } else if (isProjectTitleLine(line)) {
            flush();
            title = line.replace(/[:\s]+$/, '');
        } else if (title && !desc.length && isProjectTitleContinuation(line)) {
            title = `${title} ${line}`.trim();
        } else {
            desc.push(line);
        }
    });
    flush();

    return out;
}

const SKILL_SUBHEADERS = new Set([
    'programming skills',
    'programming languages',
    'development skills',
    'wireframe and mockups',
    'operating systems',
    'visualization programs',
    'tools',
    'technologies',
    'frameworks',
    'libraries',
    'databases',
    'cloud platforms',
    'core skills'
]);

function normalizeSkillHeader(label) {
    const normalized = String(label || '').trim().replace(/[:\-]+$/, '').toLowerCase();
    if (normalized === 'programming languages') return 'Programming Skills';
    if (normalized === 'programming skills') return 'Programming Skills';
    if (normalized === 'core skills') return 'Core Skills';
    if (normalized === 'development skills') return 'Development Skills';
    if (normalized === 'wireframe and mockups') return 'Wireframe and Mockups';
    if (normalized === 'operating systems') return 'Operating Systems';
    if (normalized === 'visualization programs') return 'Visualization Programs';
    if (normalized === 'cloud') return 'Cloud Platforms';
    if (normalized === 'cloud platforms') return 'Cloud Platforms';
    if (normalized === 'tools') return 'Tools';
    if (normalized === 'technologies') return 'Technologies';
    if (normalized === 'frameworks') return 'Frameworks';
    if (normalized === 'libraries') return 'Libraries';
    if (normalized === 'databases') return 'Databases';
    return '';
}

function isEducationLevelLine(line) {
    const text = String(line || '').trim();
    if (!text) return false;
    return /\b(bachelor|master|phd|doctorate|associate|diploma|secondary|high school|intermediate|see|b\.?s\.?|m\.?s\.?|hseb|\+2)\b/i.test(text);
}

function mergeParagraphLines(lines) {
    const cleaned = (lines || [])
        .map((line) => String(line || '').trim())
        .filter(Boolean);
    if (!cleaned.length) return [];

    const merged = [cleaned[0]];
    for (let i = 1; i < cleaned.length; i += 1) {
        const line = cleaned[i];
        const previous = merged[merged.length - 1];
        const hardBreak = /[.!?]$/.test(previous) || isEducationLevelLine(line) || /^[-•]/.test(line);
        if (hardBreak) {
            merged.push(line);
        } else {
            merged[merged.length - 1] = `${previous} ${line}`.replace(/\s+/g, ' ').trim();
        }
    }
    return merged;
}

function splitEducationEntries(lines) {
    const entries = [];
    let current = null;

    const flush = () => {
        if (current) {
            current.details = mergeParagraphLines(current.details || []);
            entries.push(current);
        }
        current = null;
    };

    (lines || []).forEach((raw) => {
        const line = String(raw || '').trim();
        if (!line) return;
        if (isEducationLevelLine(line)) {
            flush();
            current = { level: line, details: [] };
            return;
        }
        if (!current) {
            current = { level: '', details: [] };
        }
        current.details.push(line);
    });

    flush();
    return entries;
}

function parseProjectLine(line) {
    const text = String(line || '').trim();
    const idx = text.indexOf(':');
    if (idx <= 0) {
        return { title: text, description: '' };
    }
    return {
        title: text.slice(0, idx).trim(),
        description: text.slice(idx + 1).trim()
    };
}

function renderSkillsLineHtml(line) {
    const text = String(line || '').trim();
    const idx = text.indexOf(':');
    if (idx > 0) {
        const maybeHeader = normalizeSkillHeader(text.slice(0, idx));
        if (maybeHeader) {
            const rest = text.slice(idx + 1).trim();
            return `<div class="resume-line resume-skill-line"><strong class="resume-skill-header">${escapeHtml(maybeHeader)}:</strong> ${escapeHtml(rest)}</div>`;
        }
    }

    const lower = text.toLowerCase();
    for (const header of SKILL_SUBHEADERS) {
        if (lower === header) {
            return `<div class="resume-line resume-skill-line"><strong class="resume-skill-header">${escapeHtml(normalizeSkillHeader(header) || header)}:</strong></div>`;
        }
    }

    return `<div class="resume-line">${escapeHtml(text)}</div>`;
}

function renderResumeSectionHtml(section) {
    const sectionName = String(section.name || '').toUpperCase();
    const lines = Array.isArray(section.lines) ? section.lines : [];

    if (sectionName === 'PROFILE' || sectionName === 'SUMMARY') {
        const merged = mergeParagraphLines(lines);
        return `
            <section class="resume-section-block resume-section-profile">
                <h4 class="resume-section-heading"><strong>${escapeHtml(section.name)}</strong></h4>
                <div class="resume-section-rule"></div>
                <div class="resume-section-lines resume-profile-lines">
                    ${merged.map((line) => `<div class="resume-line">${escapeHtml(line)}</div>`).join('')}
                </div>
            </section>
        `;
    }

    if (sectionName === 'EDUCATION') {
        const entries = splitEducationEntries(lines);
        return `
            <section class="resume-section-block">
                <h4 class="resume-section-heading"><strong>${escapeHtml(section.name)}</strong></h4>
                <div class="resume-section-rule"></div>
                <div class="resume-section-lines resume-education-lines">
                    ${entries.map((entry) => `
                        <div class="resume-education-item">
                            ${entry.level ? `<div class="resume-education-level"><strong>${escapeHtml(entry.level)}</strong></div>` : ''}
                            ${(entry.details || []).map((detail) => `<div class="resume-line">${escapeHtml(detail)}</div>`).join('')}
                        </div>
                    `).join('')}
                </div>
            </section>
        `;
    }

    if (sectionName === 'PROJECTS') {
        const projectLines = formatProjectLines(lines);
        return `
            <section class="resume-section-block">
                <h4 class="resume-section-heading"><strong>${escapeHtml(section.name)}</strong></h4>
                <div class="resume-section-rule"></div>
                <div class="resume-section-lines resume-project-lines">
                    ${projectLines.map((line) => {
                        const project = parseProjectLine(line);
                        if (!project.description) {
                            return `<div class="resume-project-item"><div class="resume-line"><strong class="resume-project-title">${escapeHtml(project.title)}</strong></div></div>`;
                        }
                        return `
                            <div class="resume-project-item">
                                <div class="resume-line">
                                    <strong class="resume-project-title">${escapeHtml(project.title)}:</strong>
                                    <span class="resume-project-description"> ${escapeHtml(project.description)}</span>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </section>
        `;
    }

    if (sectionName === 'SKILLS') {
        return `
            <section class="resume-section-block">
                <h4 class="resume-section-heading"><strong>${escapeHtml(section.name)}</strong></h4>
                <div class="resume-section-rule"></div>
                <div class="resume-section-lines resume-skills-lines">
                    ${lines.map((line) => renderSkillsLineHtml(line)).join('')}
                </div>
            </section>
        `;
    }

    return `
        <section class="resume-section-block">
            <h4 class="resume-section-heading"><strong>${escapeHtml(section.name)}</strong></h4>
            <div class="resume-section-rule"></div>
            <div class="resume-section-lines">
                ${lines.map((line) => `<div class="resume-line">${escapeHtml(line)}</div>`).join('')}
            </div>
        </section>
    `;
}

function splitResumeForFormatting(text) {
    const lines = String(text || '')
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .split('\n')
        .map((line) => line.trimEnd());

    const sections = [];
    const headerLines = [];
    let current = null;
    let encounteredSection = false;

    lines.forEach((rawLine) => {
        const line = rawLine.trim();
        if (!line) {
            return;
        }
        if (isUnderlineLine(line)) {
            return;
        }
        if (isResumeSectionHeading(line)) {
            encounteredSection = true;
            current = { name: line.replace(/[:\-]+$/, '').toUpperCase(), lines: [] };
            sections.push(current);
            return;
        }

        if (!encounteredSection) {
            headerLines.push(line);
            return;
        }

        if (!current) {
            current = { name: 'OTHER', lines: [] };
            sections.push(current);
        }
        current.lines.push(line);
    });

    const normalizedSections = sections.map((section) => {
        if (section.name === 'PROJECTS') {
            return { ...section, lines: formatProjectLines(section.lines) };
        }
        if (section.name === 'PROFILE' || section.name === 'SUMMARY') {
            return { ...section, lines: mergeParagraphLines(section.lines) };
        }
        return section;
    });

    return { headerLines, sections: normalizedSections };
}

function renderFormattedResumeHtml(text) {
    const structured = splitResumeForFormatting(text);
    const headerHtml = structured.headerLines.length
        ? `
            <div class="resume-header-centered">
                ${structured.headerLines.map((line) => `<div class="resume-header-line">${escapeHtml(line)}</div>`).join('')}
            </div>
        `
        : '';

    const sectionsHtml = structured.sections.map((section) => renderResumeSectionHtml(section)).join('');

    return `<div class="formatted-resume">${headerHtml}${sectionsHtml}</div>`;
}

function normalizeDevelopmentStep(step) {
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

    const text = String(step || '').trim();
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

/**
 * Display skills gap analysis results
 */
function displaySkillsGap(data) {
    const gapResults = document.getElementById('gap-results');
    const gapContent = document.getElementById('gap-content');
    
    let html = '<div class="gap-analysis">';
    
    const matchingSkills = data.matching_skills || data.matched_skills || [];
    const missingSkills = data.missing_skills || [];
    const readinessScore = Number.isFinite(data.ats_score)
        ? data.ats_score
        : (Number.isFinite(data.readiness_score) ? data.readiness_score : 0);
    const totalTargetSkills = Number.isFinite(data.total_target_skills)
        ? data.total_target_skills
        : matchingSkills.length + missingSkills.length;

    if (matchingSkills.length > 0) {
        html += `
            <div class="skills-section">
                <h4 class="skills-heading success-heading">✅ Matching Skills</h4>
                <div class="skills-tags">
                    ${matchingSkills.map(skill => `<span class="skill-tag skill-match">${skill}</span>`).join('')}
                </div>
            </div>
        `;
    }
    
    if (missingSkills.length > 0) {
        html += `
            <div class="skills-section">
                <h4 class="skills-heading warning-heading">⚠️ Skills to Develop</h4>
                <div class="skills-tags">
                    ${missingSkills.map(skill => `<span class="skill-tag skill-missing">${skill}</span>`).join('')}
                </div>
            </div>
        `;
    }
    
    if (data.recommendations) {
        html += `
            <div class="skills-section">
                <h4 class="skills-heading">💡 Recommendations</h4>
                <p class="recommendations-text">${data.recommendations}</p>
            </div>
        `;
    }

    html += renderGapVisuals({
        matchingSkills,
        missingSkills,
        readinessScore,
        totalTargetSkills,
        prioritizedGaps: data.prioritized_gaps || [],
        categoryBreakdown: data.category_breakdown || [],
        strengths: data.strengths || [],
        developmentPlan: data.development_plan || []
    });

    if (data.analysis_engine) {
        html += `
            <div class="skills-section">
                <h4 class="skills-heading">Analysis Engine</h4>
                <p class="recommendations-text">${escapeHtml(data.analysis_engine)}</p>
            </div>
        `;
    }

    // If the API returns a different structure, display as JSON
    if (!matchingSkills.length && !missingSkills.length) {
        html += `<pre class="json-display">${JSON.stringify(data, null, 2)}</pre>`;
    }
    
    html += '</div>';
    
    gapContent.innerHTML = html;
    gapResults.style.display = 'block';
    
    // Scroll to results
    setTimeout(() => {
        gapResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

function renderGapVisuals(analysis) {
    const matchingSkills = analysis.matchingSkills;
    const missingSkills = analysis.missingSkills;
    const total = analysis.totalTargetSkills || (matchingSkills.length + missingSkills.length);
    const matchPct = total ? Math.round((matchingSkills.length / total) * 100) : 0;
    const missingPct = total ? 100 - matchPct : 0;

    const categoryRows = (analysis.categoryBreakdown || []).slice(0, 8).map(item => {
        const label = item.category.replace(/_/g, ' ').toUpperCase();
        return `
            <div class="category-row">
                <div class="category-meta">
                    <span class="category-name">${label}</span>
                    <span class="category-score">${item.coverage}%</span>
                </div>
                <div class="category-track">
                    <span class="category-fill" style="width: ${item.coverage}%"></span>
                </div>
                <div class="category-counts">${item.matched} matched / ${item.missing} missing</div>
            </div>
        `;
    }).join('');

    const prioritizedRows = (analysis.prioritizedGaps || []).slice(0, 10).map(item => `
        <tr>
            <td>${item.skill}</td>
            <td><span class="priority-badge priority-${String(item.priority).toLowerCase()}">${item.priority}</span></td>
            <td>${item.mention_count}</td>
        </tr>
    `).join('');

    const strengthTags = (analysis.strengths || []).slice(0, 6).map(skill => `
        <span class="skill-tag skill-match">${skill}</span>
    `).join('');

    const planItems = (analysis.developmentPlan || [])
        .map(normalizeDevelopmentStep)
        .filter(Boolean)
        .slice(0, 5)
        .map(step => `
            <li>${step}</li>
        `).join('');

    return `
        <div class="insight-grid">
            <div class="insight-card">
                <div class="insight-title">ATS Readiness Score</div>
                <div class="insight-value">${analysis.readinessScore}%</div>
                <div class="insight-subtitle">Composite score: skill match + ATS formatting</div>
            </div>
            <div class="insight-card">
                <div class="insight-title">Target Skills</div>
                <div class="insight-value">${total}</div>
                <div class="insight-subtitle">Skills detected in job description</div>
            </div>
            <div class="insight-card">
                <div class="insight-title">Missing Skills</div>
                <div class="insight-value">${missingSkills.length}</div>
                <div class="insight-subtitle">Gaps to prioritize</div>
            </div>
        </div>

        <div class="readiness-meter">
            <div class="readiness-fill" style="width: ${analysis.readinessScore}%"></div>
        </div>

        <div class="gap-visuals">
            <div class="visual-card">
                <div class="visual-title">Coverage Donut</div>
                <div class="donut" style="--match: ${matchPct};"></div>
                <div class="donut-label">${matchPct}% matched</div>
            </div>
            <div class="visual-card">
                <div class="visual-title">Matched vs Missing Mix</div>
                <div class="stack-bar">
                    <span class="stack-segment stack-match" style="width: ${matchPct}%"></span>
                    <span class="stack-segment stack-missing" style="width: ${missingPct}%"></span>
                </div>
                <div class="stack-legend">
                    <span>Matched: ${matchingSkills.length}</span>
                    <span>Missing: ${missingSkills.length}</span>
                </div>
            </div>
            <div class="visual-card">
                <div class="visual-title">Gap Distribution</div>
                <div class="bar-chart">
                    <div class="bar bar-match" style="height: ${matchPct}%">
                        ${matchingSkills.length}
                    </div>
                    <div class="bar bar-missing" style="height: ${missingPct}%">
                        ${missingSkills.length}
                    </div>
                </div>
                <div class="bar-labels">
                    <span>Matched</span>
                    <span>Missing</span>
                </div>
            </div>
        </div>

        <div class="deep-insights-grid">
            <div class="visual-card">
                <div class="visual-title">Category Coverage</div>
                <div class="category-breakdown">
                    ${categoryRows || '<div class="insight-subtitle">No category data available.</div>'}
                </div>
            </div>
            <div class="visual-card">
                <div class="visual-title">Priority Gaps</div>
                <div class="priority-table-wrap">
                    <table class="priority-table">
                        <thead>
                            <tr>
                                <th>Skill</th>
                                <th>Priority</th>
                                <th>Mentions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${prioritizedRows || '<tr><td colspan="3">No missing skills.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="deep-insights-grid">
            <div class="visual-card">
                <div class="visual-title">Current Strengths</div>
                <div class="skills-tags">${strengthTags || '<span class="insight-subtitle">No strengths identified.</span>'}</div>
            </div>
            <div class="visual-card">
                <div class="visual-title">Suggested Action Plan</div>
                <ol class="plan-list">${planItems || '<li>No immediate action items.</li>'}</ol>
            </div>
        </div>
    `;
}

/**
 * Display cover letter results
 */
function displayCoverLetter(data) {
    const coverLetterResults = document.getElementById('cover-letter-results');
    const coverLetterContent = document.getElementById('cover-letter-content');
    
    const coverLetter = sanitizeCoverLetterText(data.cover_letter || data);
    if (typeof window !== 'undefined') {
        window.__latestCoverLetterText = String(coverLetter || '');
    }
    
    coverLetterContent.innerHTML = `
        <div class="cover-letter-display">
            <pre class="cover-letter-text">${escapeHtml(coverLetter)}</pre>
        </div>
    `;
    
    coverLetterResults.style.display = 'block';
    
    // Scroll to results
    setTimeout(() => {
        coverLetterResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

/**
 * Display resume update suggestions
 */
function displayResumeUpdate(data) {
    const resumeUpdateResults = document.getElementById('resume-update-results');
    const resumeUpdateContent = document.getElementById('resume-update-content');
    
    let html = '<div class="resume-updates">';
    if (typeof window !== 'undefined') {
        window.__latestUpdatedResumeText = String(data.updated_resume || '');
    }

    if (Number.isFinite(data.ats_current_score) || Number.isFinite(data.ats_updated_score)) {
        const currentScore = Number.isFinite(data.ats_current_score) ? data.ats_current_score : 0;
        const updatedScore = Number.isFinite(data.ats_updated_score) ? data.ats_updated_score : 0;
        const delta = Number.isFinite(data.ats_score_delta) ? data.ats_score_delta : (updatedScore - currentScore);
        const trendClass = delta >= 0 ? 'score-positive' : 'score-negative';

        html += `
            <div class="ats-score-panel">
                <div class="ats-score-card">
                    <span class="ats-score-label">Current ATS Score</span>
                    <span class="ats-score-value">${currentScore}%</span>
                </div>
                <div class="ats-score-card">
                    <span class="ats-score-label">Updated ATS Score</span>
                    <span class="ats-score-value">${updatedScore}%</span>
                </div>
                <div class="ats-score-card">
                    <span class="ats-score-label">Score Delta</span>
                    <span class="ats-score-value ${trendClass}">${delta >= 0 ? '+' : ''}${delta}%</span>
                </div>
            </div>
        `;
    }
    
    if (data.suggestions && Array.isArray(data.suggestions)) {
        html += '<ul class="update-list">';
        data.suggestions.forEach(suggestion => {
            html += `<li class="update-item">💡 ${escapeHtml(suggestion)}</li>`;
        });
        html += '</ul>';
    } else if (data.updated_resume) {
        html += `<div class="update-text">${renderFormattedResumeHtml(data.updated_resume)}</div>`;
    } else if (typeof data === 'string') {
        html += `<div class="update-text">${renderFormattedResumeHtml(data)}</div>`;
    } else {
        html += `<pre class="json-display">${JSON.stringify(data, null, 2)}</pre>`;
    }
    
    html += '</div>';
    
    resumeUpdateContent.innerHTML = html;
    resumeUpdateResults.style.display = 'block';
    
    // Scroll to results
    setTimeout(() => {
        resumeUpdateResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

/**
 * Display job recommendation results
 */
function displayJobRecommendations(data) {
    const jobResults = document.getElementById('job-results');
    const jobContent = document.getElementById('job-content');
    const jobs = data.jobs || [];

    let html = `
        <div class="job-summary">
            <div><strong>Inferred Role:</strong> ${escapeHtml(data.inferred_role || 'Not specified')}</div>
            <div><strong>Inferred Location:</strong> ${escapeHtml(data.inferred_location || 'Not specified')}</div>
        </div>
    `;

    if (!jobs.length) {
        html += `<div class="job-empty">No live listings were returned by Tavily. Confirm internet access and TAVILY_API_KEY, then try again.</div>`;
    } else {
        html += '<div class="job-listings">';
        jobs.forEach(job => {
            const skills = (job.matched_skills || []).slice(0, 6);
            const safeUrl = sanitizeUrl(job.url || '');
            html += `
                <article class="job-card">
                    <div class="job-top-row">
                        <h4 class="job-title">${escapeHtml(job.title)}</h4>
                        <span class="job-score">${escapeHtml(job.compatibility_score)}% match</span>
                    </div>
                    <div class="job-meta">${escapeHtml(job.company)} • ${escapeHtml(job.location)} • ${escapeHtml(job.source)}</div>
                    <div class="job-skills">
                        ${skills.map(skill => `<span class="job-skill">${escapeHtml(skill)}</span>`).join('')}
                    </div>
                    <a class="job-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">View Job Listing</a>
                </article>
            `;
        });
        html += '</div>';
    }

    jobContent.innerHTML = html;
    jobResults.style.display = 'block';

    setTimeout(() => {
        jobResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

/**
 * Display parsed resume text
 */
function displayResumeText(text) {
    const resumeDisplay = document.getElementById('resume-display');
    const resumeTextContent = document.getElementById('resume-text-content');
    
    resumeTextContent.innerHTML = `<pre class="resume-parsed-text">${text}</pre>`;
    resumeDisplay.style.display = 'block';
    
    // Scroll to display
    setTimeout(() => {
        resumeDisplay.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

/**
 * Close result card
 */
function closeResult(resultId) {
    const resultCard = document.getElementById(resultId);
    if (resultCard) {
        resultCard.style.display = 'none';
    }
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const text = element.innerText || element.textContent;
    
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard!', 'success');
    } catch (err) {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        
        try {
            document.execCommand('copy');
            showToast('Copied to clipboard!', 'success');
        } catch (err) {
            showToast('Failed to copy', 'error');
        }
        
        document.body.removeChild(textarea);
    }
}

/**
 * Download text as file
 */
function downloadText(elementId, filename) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const text = element.innerText || element.textContent;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('Download started!', 'success');
}

function _getPdfConstructor() {
    if (typeof window === 'undefined') {
        return null;
    }
    if (window.jspdf && window.jspdf.jsPDF) {
        return window.jspdf.jsPDF;
    }
    return null;
}

function _buildPdf(text, filename, title = '') {
    const jsPDF = _getPdfConstructor();
    if (!jsPDF) {
        throw new Error('PDF library unavailable');
    }

    const content = String(text || '').replace(/\r\n/g, '\n').trim();
    if (!content) {
        throw new Error('No content to export');
    }

    const doc = new jsPDF({ unit: 'pt', format: 'a4' });
    const pageHeight = doc.internal.pageSize.getHeight();
    const pageWidth = doc.internal.pageSize.getWidth();
    const margin = 52;
    const maxWidth = pageWidth - (margin * 2);
    let y = margin;

    if (title) {
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(14);
        doc.text(title, margin, y);
        y += 26;
    }

    const isResume = /updated-resume/i.test(filename || '') || /updated resume/i.test(title || '');
    doc.setFont(isResume ? 'helvetica' : 'times', 'normal');
    doc.setFontSize(isResume ? 10.5 : 11);

    if (isResume) {
        const structured = splitResumeForFormatting(content);
        const centerX = pageWidth / 2;

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(11);
        structured.headerLines.forEach((line) => {
            if (y > pageHeight - margin) {
                doc.addPage();
                y = margin;
            }
            const wrapped = doc.splitTextToSize(line, maxWidth * 0.85);
            wrapped.forEach((chunk) => {
                doc.text(chunk, centerX, y, { align: 'center' });
                y += 14;
            });
        });

        if (structured.headerLines.length) {
            y += 6;
        }

        structured.sections.forEach((section) => {
            if (y > pageHeight - margin - 40) {
                doc.addPage();
                y = margin;
            }

            doc.setFont('helvetica', 'bold');
            doc.setFontSize(11.5);
            doc.text(section.name, margin, y);
            y += 6;
            doc.setLineWidth(0.8);
            doc.line(margin, y, margin + maxWidth, y);
            y += 10;

            const sectionName = String(section.name || '').toUpperCase();
            const sectionLines = Array.isArray(section.lines) ? section.lines : [];

            const drawWrapped = (text, x, width, fontStyle = 'normal') => {
                doc.setFont('helvetica', fontStyle);
                doc.setFontSize(10.5);
                const wrapped = doc.splitTextToSize(String(text || ''), width);
                wrapped.forEach((chunk) => {
                    if (y > pageHeight - margin) {
                        doc.addPage();
                        y = margin;
                    }
                    doc.text(chunk, x, y);
                    y += 14;
                });
            };

            if (sectionName === 'PROJECTS') {
                sectionLines.forEach((line) => {
                    const parsed = parseProjectLine(line);
                    if (parsed.title) {
                        drawWrapped(`${parsed.title}:`, margin, maxWidth, 'bold');
                    }
                    if (parsed.description) {
                        drawWrapped(parsed.description, margin + 12, maxWidth - 12, 'normal');
                    }
                    y += 6;
                });
            } else if (sectionName === 'EDUCATION') {
                sectionLines.forEach((line) => {
                    if (isEducationLevelLine(line)) {
                        y += 3;
                        drawWrapped(line, margin, maxWidth, 'bold');
                    } else {
                        drawWrapped(line, margin + 10, maxWidth - 10, 'normal');
                    }
                });
            } else if (sectionName === 'SKILLS') {
                sectionLines.forEach((line) => {
                    const idx = String(line || '').indexOf(':');
                    if (idx > 0) {
                        const rawHeader = String(line).slice(0, idx).trim();
                        const normalizedHeader = normalizeSkillHeader(rawHeader);
                        if (normalizedHeader) {
                            drawWrapped(`${normalizedHeader}:`, margin, maxWidth, 'bold');
                            const details = String(line).slice(idx + 1).trim();
                            if (details) {
                                drawWrapped(details, margin + 12, maxWidth - 12, 'normal');
                            }
                            return;
                        }
                    }
                    drawWrapped(line, margin, maxWidth, 'normal');
                });
            } else {
                sectionLines.forEach((line) => {
                    drawWrapped(line, margin, maxWidth, 'normal');
                });
            }
            y += 8;
        });
    } else {
        const lines = doc.splitTextToSize(content, maxWidth);
        lines.forEach((line) => {
            if (y > pageHeight - margin) {
                doc.addPage();
                y = margin;
            }
            doc.text(line, margin, y);
            y += 16;
        });
    }

    doc.save(filename.toLowerCase().endsWith('.pdf') ? filename : `${filename}.pdf`);
}

function sanitizeCoverLetterText(rawText) {
    const text = String(rawText || '')
        .replace(/\r\n/g, '\n')
        .replace(/^```[a-zA-Z]*\n?/i, '')
        .replace(/\n?```$/i, '')
        .trim();

    if (!text) {
        return '';
    }

    const lines = text
        .split('\n')
        .map((line) => line.replace(/^#{1,6}\s*/, '').replace(/^\*\*(.*)\*\*$/, '$1'));

    const introPattern = /^(cover letter|generated cover letter|professional cover letter|here(?:'s| is)|below is|certainly|of course|sure|the following|i have generated|i've generated|this is)\b/i;
    const trailingPattern = /^(let me know|feel free|if you want|if you'd like|i can|note:|tips?:)/i;
    let start = 0;
    let end = lines.length - 1;

    while (start <= end) {
        const line = lines[start].trim();
        if (!line || introPattern.test(line)) {
            start += 1;
            continue;
        }
        break;
    }

    while (end >= start) {
        const line = lines[end].trim();
        if (!line || trailingPattern.test(line)) {
            end -= 1;
            continue;
        }
        break;
    }

    return lines.slice(start, end + 1).join('\n').trim();
}

function downloadGeneratedPdf(text, filename, title = '') {
    try {
        const cleanText = (/cover\s*letter/i.test(title) || /cover\s*letter/i.test(filename))
            ? sanitizeCoverLetterText(text)
            : text;
        _buildPdf(cleanText, filename, title);
        showToast('PDF download started!', 'success');
    } catch (error) {
        console.error('PDF export error:', error);
        showToast('Unable to export PDF. Please refresh and try again.', 'error');
    }
}

function downloadCoverLetterPdf() {
    const content = (typeof window !== 'undefined' && window.__latestCoverLetterText)
        ? window.__latestCoverLetterText
        : (document.getElementById('cover-letter-content')?.innerText || '');
    downloadGeneratedPdf(content, 'cover-letter.pdf', '');
}

function downloadUpdatedResumePdf() {
    const content = (typeof window !== 'undefined' && window.__latestUpdatedResumeText)
        ? window.__latestUpdatedResumeText
        : (document.querySelector('#resume-update-content .update-text')?.innerText || '');
    downloadGeneratedPdf(content, 'updated-resume.pdf', '');
}

/**
 * Validate file type
 */
function validateFileType(file, allowedTypes) {
    const fileExtension = file.name.split('.').pop().toLowerCase();
    return allowedTypes.some(type => type.includes(fileExtension));
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Enable/disable action buttons based on state
 */
function updateActionButtonsState(hasResume, hasJobDescription) {
    const analyzeBtn = document.getElementById('analyze-gap-btn');
    const coverLetterBtn = document.getElementById('generate-cover-letter-btn');
    const updateResumeBtn = document.getElementById('update-resume-btn');
    const findJobsBtn = document.getElementById('find-jobs-btn');
    
    const isReady = hasResume && hasJobDescription;
    
    analyzeBtn.disabled = !isReady;
    coverLetterBtn.disabled = !isReady;
    updateResumeBtn.disabled = !isReady;
    if (findJobsBtn) {
        findJobsBtn.disabled = !(hasResume && hasJobDescription);
    }
}

/**
 * Show results container
 */
function showResultsContainer() {
    const resultsContainer = document.getElementById('results-container');
    if (resultsContainer.style.display === 'none') {
        resultsContainer.style.display = 'block';
    }
}

// Export functions for global use
if (typeof window !== 'undefined') {
    window.showLoading = showLoading;
    window.hideLoading = hideLoading;
    window.showToast = showToast;
    window.displaySkillsGap = displaySkillsGap;
    window.displayCoverLetter = displayCoverLetter;
    window.displayResumeUpdate = displayResumeUpdate;
    window.displayJobRecommendations = displayJobRecommendations;
    window.displayResumeText = displayResumeText;
    window.closeResult = closeResult;
    window.copyToClipboard = copyToClipboard;
    window.downloadText = downloadText;
    window.downloadGeneratedPdf = downloadGeneratedPdf;
    window.downloadCoverLetterPdf = downloadCoverLetterPdf;
    window.downloadUpdatedResumePdf = downloadUpdatedResumePdf;
    window.sanitizeCoverLetterText = sanitizeCoverLetterText;
    window.validateFileType = validateFileType;
    window.formatFileSize = formatFileSize;
    window.updateActionButtonsState = updateActionButtonsState;
    window.showResultsContainer = showResultsContainer;
}
