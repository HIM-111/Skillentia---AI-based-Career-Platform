document.addEventListener('DOMContentLoaded', async function() {
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const switchToSignup = document.getElementById('switch-to-signup');
    const switchToLogin = document.getElementById('switch-to-login');
    const loginPanel = document.getElementById('login-panel');
    const signupPanel = document.getElementById('signup-panel');
    const statusEl = document.getElementById('auth-status');

    const isAuthed = await verifyAuth();
    if (isAuthed) {
        window.location.href = 'index.html';
        return;
    }

    function setStatus(message, type = 'info') {
        if (!statusEl) return;
        statusEl.textContent = message;
        statusEl.className = `auth-status ${type}`;
    }

    function showLogin() {
        loginPanel.style.display = 'block';
        signupPanel.style.display = 'none';
        setStatus('');
    }

    function showSignup() {
        loginPanel.style.display = 'none';
        signupPanel.style.display = 'block';
        setStatus('');
    }

    switchToSignup?.addEventListener('click', function(event) {
        event.preventDefault();
        showSignup();
    });

    switchToLogin?.addEventListener('click', function(event) {
        event.preventDefault();
        showLogin();
    });

    loginForm?.addEventListener('submit', async function(event) {
        event.preventDefault();
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;

        try {
            setStatus('Signing in...', 'loading');
            const response = await APIService.login(email, password);
            saveAuthSession(response.token, response.user);
            window.location.href = 'index.html';
        } catch (error) {
            setStatus(error.message, 'error');
        }
    });

    signupForm?.addEventListener('submit', async function(event) {
        event.preventDefault();
        const email = document.getElementById('signup-email').value.trim();
        const password = document.getElementById('signup-password').value;
        const confirm = document.getElementById('signup-confirm').value;

        if (password !== confirm) {
            setStatus('Passwords do not match.', 'error');
            return;
        }

        try {
            setStatus('Creating account...', 'loading');
            const response = await APIService.signup(email, password);
            saveAuthSession(response.token, response.user);
            window.location.href = 'index.html';
        } catch (error) {
            setStatus(error.message, 'error');
        }
    });
});
