const AUTH_TOKEN_KEY = 'careerPlatformAuthToken';
const AUTH_USER_KEY = 'careerPlatformAuthUser';

function saveAuthSession(token, user) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user || {}));
}

function clearAuthSession() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    localStorage.removeItem('careerPlatformResumeText');
    localStorage.removeItem('careerPlatformJobDescription');
    localStorage.removeItem('careerPlatformFeatureResults');
}

function getAuthToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY) || '';
}

function getAuthUser() {
    try {
        return JSON.parse(localStorage.getItem(AUTH_USER_KEY) || '{}');
    } catch (error) {
        return {};
    }
}

function requireAuth(redirectTo = 'auth.html') {
    const token = getAuthToken();
    if (!token) {
        window.location.href = redirectTo;
        return false;
    }
    return true;
}

async function verifyAuth() {
    const token = getAuthToken();
    if (!token) {
        return false;
    }
    try {
        await APIService.getCurrentUser();
        return true;
    } catch (error) {
        clearAuthSession();
        return false;
    }
}

async function logoutAndRedirect() {
    try {
        await APIService.logout();
    } catch (error) {
        // Ignore backend logout failures; local session is still removed.
    }
    clearAuthSession();
    window.location.href = 'auth.html';
}

function bindLogoutButtons() {
    document.querySelectorAll('[data-logout]').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.preventDefault();
            logoutAndRedirect();
        });
    });
}

if (typeof window !== 'undefined') {
    window.saveAuthSession = saveAuthSession;
    window.clearAuthSession = clearAuthSession;
    window.getAuthToken = getAuthToken;
    window.getAuthUser = getAuthUser;
    window.requireAuth = requireAuth;
    window.verifyAuth = verifyAuth;
    window.logoutAndRedirect = logoutAndRedirect;
    window.bindLogoutButtons = bindLogoutButtons;
}
