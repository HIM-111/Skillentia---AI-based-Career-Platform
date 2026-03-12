const FEATURE_RESULT_CACHE_KEY = 'careerPlatformFeatureResults';
const FEATURE_RESULT_CACHE_VERSION = 'v2';

function simpleHash(input) {
    let hash = 0;
    const text = String(input || '');
    for (let i = 0; i < text.length; i += 1) {
        hash = ((hash << 5) - hash) + text.charCodeAt(i);
        hash |= 0;
    }
    return String(hash);
}

function getCachedFeatureStore() {
    try {
        return JSON.parse(localStorage.getItem(FEATURE_RESULT_CACHE_KEY) || '{}');
    } catch (_error) {
        return {};
    }
}

function setCachedFeatureStore(store) {
    localStorage.setItem(FEATURE_RESULT_CACHE_KEY, JSON.stringify(store || {}));
}

function getCurrentUserCacheBucket() {
    const user = (typeof getAuthUser === 'function' ? getAuthUser() : {}) || {};
    const userId = user.id ? String(user.id) : 'anonymous';
    const store = getCachedFeatureStore();
    return {
        store,
        userId,
        userBucket: (store[userId] && typeof store[userId] === 'object') ? store[userId] : {}
    };
}

function saveFeatureResult(feature, contextHash, payload) {
    const { store, userId, userBucket } = getCurrentUserCacheBucket();
    userBucket[feature] = {
        context_hash: contextHash,
        updated_at: new Date().toISOString(),
        payload
    };
    store[userId] = userBucket;
    setCachedFeatureStore(store);
}

function getFeatureResult(feature, contextHash) {
    const { userBucket } = getCurrentUserCacheBucket();
    const entry = userBucket[feature];
    if (!entry || entry.context_hash !== contextHash) {
        return null;
    }
    return entry.payload || null;
}

function renderFeatureResult(feature, payload) {
    if (!payload) {
        return false;
    }

    if (feature === 'gap') {
        displaySkillsGap(payload);
        showResultsContainer();
        return true;
    }
    if (feature === 'cover-letter') {
        displayCoverLetter(payload);
        showResultsContainer();
        return true;
    }
    if (feature === 'resume-updater') {
        displayResumeUpdate(payload);
        showResultsContainer();
        return true;
    }
    if (feature === 'jobs') {
        displayJobRecommendations(payload);
        showResultsContainer();
        return true;
    }

    return false;
}

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

    const feature = document.body.dataset.feature;
    const runButton = document.getElementById('run-feature-btn');
    const missingContext = document.getElementById('missing-context');
    if (!runButton) {
        return;
    }

    async function initFeaturePage() {
        let resumeText = '';
        let jobDescription = '';

        try {
            const context = await APIService.getUserContext();
            resumeText = (context.resume_text || '').trim();
            jobDescription = (context.job_description || '').trim();
        } catch (_error) {
            if (missingContext) {
                missingContext.style.display = 'block';
                missingContext.textContent = 'Unable to load account context. Please return Home and try again.';
            }
            runButton.disabled = true;
            return;
        }

        if (!resumeText || !jobDescription) {
            if (missingContext) {
                missingContext.style.display = 'block';
            }
            runButton.disabled = true;
            return;
        }

        if (missingContext) {
            missingContext.style.display = 'none';
        }

        const contextHash = simpleHash(`${FEATURE_RESULT_CACHE_VERSION}\n${resumeText}\n---\n${jobDescription}`);
        const cachedPayload = getFeatureResult(feature, contextHash);
        const hasCachedResult = renderFeatureResult(feature, cachedPayload);

        async function runFeature() {
            showLoading('Running analysis...');
            try {
                if (feature === 'gap') {
                    const response = await APIService.analyzeSkillsGap(resumeText, jobDescription);
                    renderFeatureResult(feature, response);
                    saveFeatureResult(feature, contextHash, response);
                }
                if (feature === 'cover-letter') {
                    const response = await APIService.generateCoverLetter(resumeText, jobDescription);
                    renderFeatureResult(feature, response);
                    saveFeatureResult(feature, contextHash, response);
                }
                if (feature === 'resume-updater') {
                    const response = await APIService.updateResume(resumeText, jobDescription);
                    renderFeatureResult(feature, response);
                    saveFeatureResult(feature, contextHash, response);
                }
                if (feature === 'jobs') {
                    const response = await APIService.findJobRecommendations(resumeText, jobDescription, 5);
                    renderFeatureResult(feature, response);
                    saveFeatureResult(feature, contextHash, response);
                }
            } catch (error) {
                showToast(error.message || 'Request failed', 'error');
            } finally {
                hideLoading();
            }
        }

        runButton.addEventListener('click', runFeature);

        const params = new URLSearchParams(window.location.search);
        if (params.get('autorun') === '1' && !hasCachedResult) {
            runFeature();
        }
    }

    initFeaturePage();
});
