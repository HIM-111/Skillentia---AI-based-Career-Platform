// API Service Layer - Handles all backend communication

// Configuration
const API_BASE_URL = (() => {
    const base = window.API_BASE_URL || 'http://127.0.0.1:8000/api';
    if (base.endsWith('/api')) {
        return base;
    }
    return `${base.replace(/\/$/, '')}/api`;
})();

function getAuthToken() {
    return localStorage.getItem('careerPlatformAuthToken') || '';
}

function authHeaders(extraHeaders = {}) {
    const token = getAuthToken();
    const headers = { ...extraHeaders };
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }
    return headers;
}

// API Service Object
const APIService = {
    async signup(email, password) {
        const response = await fetch(`${API_BASE_URL}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Signup failed');
        }
        return data;
    },

    async login(email, password) {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }
        return data;
    },

    async getCurrentUser() {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            method: 'GET',
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Not authenticated');
        }
        return data;
    },

    async logout() {
        const response = await fetch(`${API_BASE_URL}/auth/logout`, {
            method: 'POST',
            headers: authHeaders()
        });
        if (!response.ok) {
            throw new Error('Logout failed');
        }
        return response.json();
    },

    async getUserContext() {
        const response = await fetch(`${API_BASE_URL}/context`, {
            method: 'GET',
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load user context');
        }
        return data;
    },

    async saveUserContext(contextPatch = {}) {
        const payload = {};
        if (Object.prototype.hasOwnProperty.call(contextPatch, 'resume_text')) {
            payload.resume_text = contextPatch.resume_text;
        }
        if (Object.prototype.hasOwnProperty.call(contextPatch, 'job_description')) {
            payload.job_description = contextPatch.job_description;
        }
        if (!Object.keys(payload).length) {
            throw new Error('No context fields provided');
        }

        const response = await fetch(`${API_BASE_URL}/context`, {
            method: 'PUT',
            headers: authHeaders({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to save user context');
        }
        return data;
    },

    async clearResumeContext() {
        const response = await fetch(`${API_BASE_URL}/context/resume`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to clear resume context');
        }
        return data;
    },

    async getDashboard() {
        const response = await fetch(`${API_BASE_URL}/dashboard`, {
            method: 'GET',
            headers: authHeaders()
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load reports');
        }
        return data;
    },

    /**
     * Upload and parse resume file
     * @param {File} file - Resume file (PDF, DOCX, DOC, or TXT)
     * @returns {Promise} Parsed resume text
     */
    async uploadResume(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${API_BASE_URL}/resume-upload`, {
                method: 'POST',
                headers: authHeaders(),
                body: formData
            });

            if (!response.ok) {
                let errorMessage = 'Failed to upload resume';
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (parseError) {
                    const text = await response.text();
                    if (text) {
                        errorMessage = text;
                    }
                }
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            console.error('Resume upload error:', error);
            throw error;
        }
    },
    
    /**
     * Analyze skills gap between resume and job description
     * @param {string} resumeText - Parsed resume text
     * @param {string} jobDescription - Job description text
     * @returns {Promise} Skills gap analysis results
     */
    async analyzeSkillsGap(resumeText, jobDescription) {
        try {
            const response = await fetch(`${API_BASE_URL}/skill-gap`, {
                method: 'POST',
                headers: authHeaders({
                    'Content-Type': 'application/json',
                }),
                body: JSON.stringify({
                    resume_text: resumeText,
                    job_description: jobDescription
                }),
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to analyze skills gap');
            }
            
            return await response.json();
        } catch (error) {
            console.error('Skills gap analysis error:', error);
            throw error;
        }
    },
    
    /**
     * Generate cover letter based on job description
     * @param {string} resumeText - Parsed resume text
     * @param {string} jobDescription - Job description text
     * @returns {Promise} Generated cover letter
     */
    async generateCoverLetter(resumeText, jobDescription) {
        try {
            const response = await fetch(`${API_BASE_URL}/cover-letter`, {
                method: 'POST',
                headers: authHeaders({
                    'Content-Type': 'application/json',
                }),
                body: JSON.stringify({
                    resume_text: resumeText,
                    job_description: jobDescription
                }),
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to generate cover letter');
            }
            
            return await response.json();
        } catch (error) {
            console.error('Cover letter generation error:', error);
            throw error;
        }
    },
    
    /**
     * Get resume update suggestions based on job description
     * @param {string} resumeText - Parsed resume text
     * @param {string} jobDescription - Job description text
     * @returns {Promise} Resume update suggestions
     */
    async updateResume(resumeText, jobDescription) {
        try {
            const response = await fetch(`${API_BASE_URL}/resume-update`, {
                method: 'POST',
                headers: authHeaders({
                    'Content-Type': 'application/json',
                }),
                body: JSON.stringify({
                    resume_text: resumeText,
                    job_description: jobDescription
                }),
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to update resume');
            }
            
            return await response.json();
        } catch (error) {
            console.error('Resume update error:', error);
            throw error;
        }
    },

    /**
     * Find resume-based job recommendations from online listings
     * @param {string} resumeText - Parsed resume text
     * @param {number} limit - Max number of jobs
     * @returns {Promise} Job recommendation response
     */
    async findJobRecommendations(resumeText, jobDescription, limit = 5) {
        try {
            const response = await fetch(`${API_BASE_URL}/job-recommendations`, {
                method: 'POST',
                headers: authHeaders({
                    'Content-Type': 'application/json',
                }),
                body: JSON.stringify({
                    resume_text: resumeText,
                    job_description: jobDescription,
                    limit
                }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to get job recommendations');
            }

            return await response.json();
        } catch (error) {
            console.error('Job recommendation error:', error);
            throw error;
        }
    }
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = APIService;
}
