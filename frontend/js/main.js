// Main JavaScript - Application Logic
let appState = {
    resumeFile: null,
    resumeText: '',
    jobDescription: '',
    hasResume: false,
    hasJobDescription: false
};

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
    
    // ===== ELEMENT REFERENCES =====
    const resumeUploadInput = document.getElementById('resume-upload');
    const resumeFileName = document.getElementById('resume-file-name');
    const uploadResumeBtn = document.getElementById('upload-resume-btn');
    const removeResumeBtn = document.getElementById('remove-resume-btn');
    const resumeStatus = document.getElementById('resume-status');
    const resumeDisplay = document.getElementById('resume-display');
    
    const jobDescriptionTextarea = document.getElementById('job-description');
    const charCount = document.getElementById('char-count');
    
    const analyzeGapBtn = document.getElementById('analyze-gap-btn');
    const generateCoverLetterBtn = document.getElementById('generate-cover-letter-btn');
    const updateResumeBtn = document.getElementById('update-resume-btn');
    const findJobsBtn = document.getElementById('find-jobs-btn');
    let jobDescriptionSaveTimer = null;

    function setCharCountColor(length) {
        if (length > 0 && length < 50) {
            charCount.style.color = 'var(--color-warning)';
            return;
        }
        if (length >= 50) {
            charCount.style.color = 'var(--color-success)';
            return;
        }
        charCount.style.color = '';
    }

    async function loadContext() {
        try {
            const context = await APIService.getUserContext();
            const resumeText = (context.resume_text || '').trim();
            const jobDescription = context.job_description || '';

            if (resumeText) {
                appState.resumeText = context.resume_text;
                appState.hasResume = true;
                resumeStatus.textContent = '✓ Resume context loaded for your account';
                resumeStatus.className = 'upload-status status-success';
                displayResumeText(context.resume_text);
                if (removeResumeBtn) {
                    removeResumeBtn.disabled = false;
                }
            }

            if (jobDescriptionTextarea) {
                jobDescriptionTextarea.value = jobDescription;
                appState.jobDescription = jobDescription;
                appState.hasJobDescription = jobDescription.trim().length > 50;
                charCount.textContent = jobDescription.length;
                setCharCountColor(jobDescription.length);
            }
        } catch (error) {
            console.error('Failed to load saved context:', error);
            showToast('Unable to load saved account context', 'warning');
        } finally {
            updateActionButtonsState(appState.hasResume, appState.hasJobDescription);
        }
    }

    function scheduleJobDescriptionSave(text) {
        if (jobDescriptionSaveTimer) {
            window.clearTimeout(jobDescriptionSaveTimer);
        }
        jobDescriptionSaveTimer = window.setTimeout(async () => {
            try {
                await APIService.saveUserContext({ job_description: text });
            } catch (error) {
                console.error('Failed to save job description context:', error);
            }
        }, 400);
    }

    loadContext();
    
    // ===== RESUME FILE SELECTION =====
    resumeUploadInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        
        if (file) {
            // Validate file type
            const allowedTypes = ['.pdf', '.docx', '.doc', '.docs', '.txt'];
            if (!validateFileType(file, allowedTypes)) {
                showToast('Please upload a PDF, DOCX, DOC/DOCS, or TXT file', 'error');
                resumeUploadInput.value = '';
                return;
            }
            
            // Validate file size (max 10MB)
            if (file.size > 10 * 1024 * 1024) {
                showToast('File size must be less than 10MB', 'error');
                resumeUploadInput.value = '';
                return;
            }
            
            appState.resumeFile = file;
            resumeFileName.textContent = `${file.name} (${formatFileSize(file.size)})`;
            resumeFileName.style.display = 'block';
            uploadResumeBtn.disabled = false;
            
            resumeStatus.textContent = '';
            resumeStatus.className = 'upload-status';
        }
    });
    
    // ===== UPLOAD RESUME BUTTON =====
    uploadResumeBtn.addEventListener('click', async function() {
        if (!appState.resumeFile) {
            showToast('Please select a file first', 'warning');
            return;
        }
        
        showLoading('Uploading and parsing resume...');
        resumeStatus.textContent = 'Uploading...';
        resumeStatus.className = 'upload-status status-loading';
        
        try {
            const response = await APIService.uploadResume(appState.resumeFile);
            
            appState.resumeText = response.resume_text;
            appState.hasResume = true;
            if (removeResumeBtn) {
                removeResumeBtn.disabled = false;
            }
            
            // Display parsed resume
            displayResumeText(response.resume_text);
            
            resumeStatus.textContent = '✓ Resume uploaded successfully';
            resumeStatus.className = 'upload-status status-success';
            
            showToast('Resume uploaded and parsed successfully!', 'success');
            
            // Update button states
            updateActionButtonsState(appState.hasResume, appState.hasJobDescription);
            
        } catch (error) {
            console.error('Upload error:', error);
            resumeStatus.textContent = '✗ Upload failed: ' + error.message;
            resumeStatus.className = 'upload-status status-error';
            showToast('Failed to upload resume: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    });

    if (removeResumeBtn) {
        removeResumeBtn.addEventListener('click', async function() {
            showLoading('Removing stored resume...');
            try {
                await APIService.clearResumeContext();

                appState.resumeFile = null;
                appState.resumeText = '';
                appState.hasResume = false;
                resumeUploadInput.value = '';
                resumeFileName.textContent = '';
                resumeFileName.style.display = 'none';
                uploadResumeBtn.disabled = true;
                removeResumeBtn.disabled = true;
                if (resumeDisplay) {
                    resumeDisplay.style.display = 'none';
                }

                resumeStatus.textContent = 'Resume removed. Upload a new resume to continue.';
                resumeStatus.className = 'upload-status status-success';
                updateActionButtonsState(appState.hasResume, appState.hasJobDescription);
                showToast('Stored resume removed', 'success');
            } catch (error) {
                console.error('Resume remove error:', error);
                resumeStatus.textContent = '✗ Failed to remove resume: ' + error.message;
                resumeStatus.className = 'upload-status status-error';
                showToast('Failed to remove resume: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        });
    }
    
    // ===== JOB DESCRIPTION INPUT =====
    jobDescriptionTextarea.addEventListener('input', function(e) {
        const text = e.target.value;
        appState.jobDescription = text;
        appState.hasJobDescription = text.trim().length > 50; // Minimum 50 characters
        scheduleJobDescriptionSave(text);
        
        // Update character count
        charCount.textContent = text.length;
        
        // Update button states
        updateActionButtonsState(appState.hasResume, appState.hasJobDescription);
        
        // Visual feedback
        setCharCountColor(text.length);
    });
    
    function openFeaturePage(path) {
        if (!appState.hasResume || !appState.hasJobDescription) {
            showToast('Please upload a resume and enter a job description', 'warning');
            return;
        }
        window.location.href = `${path}?autorun=1`;
    }

    // ===== FEATURE PAGE ROUTING =====
    analyzeGapBtn.addEventListener('click', function() {
        openFeaturePage('gap-analysis.html');
    });

    generateCoverLetterBtn.addEventListener('click', function() {
        openFeaturePage('cover-letter.html');
    });

    updateResumeBtn.addEventListener('click', function() {
        openFeaturePage('resume-updater.html');
    });

    // ===== FIND JOB MATCHES =====
    if (findJobsBtn) {
        findJobsBtn.addEventListener('click', function() {
            openFeaturePage('job-listings.html');
        });
    }
    
    // ===== MOBILE MENU TOGGLE =====
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
            
            menuToggle.setAttribute('aria-expanded', !isExpanded);
            navLinks.classList.toggle('active');
            
            // Animate hamburger icon
            const spans = menuToggle.querySelectorAll('span');
            if (navLinks.classList.contains('active')) {
                spans[0].style.transform = 'rotate(45deg) translate(8px, 8px)';
                spans[1].style.opacity = '0';
                spans[2].style.transform = 'rotate(-45deg) translate(7px, -7px)';
            } else {
                spans[0].style.transform = '';
                spans[1].style.opacity = '';
                spans[2].style.transform = '';
            }
        });
        
        // Close menu when clicking on a link
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navLinks.classList.remove('active');
                menuToggle.setAttribute('aria-expanded', 'false');
                
                const spans = menuToggle.querySelectorAll('span');
                spans[0].style.transform = '';
                spans[1].style.opacity = '';
                spans[2].style.transform = '';
            });
        });
    }
    
    // ===== NAVBAR SCROLL EFFECT =====
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 100) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
    
    // ===== SMOOTH SCROLLING =====
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            
            if (href === '#') {
                e.preventDefault();
                return;
            }
            
            const target = document.querySelector(href);
            
            if (target) {
                e.preventDefault();
                
                const navbarHeight = navbar.offsetHeight;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navbarHeight;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // ===== SCROLL REVEAL ANIMATIONS =====
    const observerOptions = {
        threshold: 0.15,
        rootMargin: '0px 0px -100px 0px'
    };
    
    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe step cards
    document.querySelectorAll('.step-card').forEach((card, index) => {
        card.classList.add('scroll-reveal');
        card.style.transitionDelay = `${index * 0.1}s`;
        observer.observe(card);
    });
    
    // ===== STATS COUNTER ANIMATION =====
    const stats = document.querySelectorAll('.stat-number');
    let hasAnimated = false;
    
    const animateStats = () => {
        if (hasAnimated) return;
        
        const heroSection = document.querySelector('.hero');
        const heroPosition = heroSection.getBoundingClientRect().top;
        const screenPosition = window.innerHeight;
        
        if (heroPosition < screenPosition) {
            hasAnimated = true;
            
            stats.forEach(stat => {
                const target = stat.textContent;
                const isPercentage = target.includes('%');
                const numericValue = parseInt(target.replace(/\D/g, ''));

                if (Number.isNaN(numericValue)) {
                    return;
                }

                const suffix = target.replace(/[0-9]/g, '');
                
                let current = 0;
                const increment = numericValue / 50;
                const timer = setInterval(() => {
                    current += increment;
                    if (current >= numericValue) {
                        stat.textContent = target;
                        clearInterval(timer);
                    } else {
                        stat.textContent = Math.floor(current) + suffix;
                    }
                }, 30);
            });
        }
    };
    
    window.addEventListener('scroll', animateStats);
    animateStats();
    
    // ===== PARALLAX EFFECT =====
    const heroBackground = document.querySelector('.hero-background');
    
    if (heroBackground) {
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const rate = scrolled * 0.5;
            heroBackground.style.transform = `translate3d(0, ${rate}px, 0)`;
        });
    }
    
    // ===== KEYBOARD NAVIGATION =====
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
            document.body.classList.add('keyboard-nav');
        }
    });
    
    window.addEventListener('mousedown', () => {
        document.body.classList.remove('keyboard-nav');
    });
    
    // ===== DRAG AND DROP FOR RESUME =====
    const uploadCard = document.querySelector('.upload-card');
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadCard.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadCard.addEventListener(eventName, () => {
            uploadCard.classList.add('drag-over');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadCard.addEventListener(eventName, () => {
            uploadCard.classList.remove('drag-over');
        }, false);
    });
    
    uploadCard.addEventListener('drop', function(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            resumeUploadInput.files = files;
            
            // Trigger change event
            const event = new Event('change', { bubbles: true });
            resumeUploadInput.dispatchEvent(event);
        }
    }, false);
    
    // ===== CONSOLE EASTER EGG =====
    console.log('%cSkillentia', 'font-size: 24px; font-weight: bold; color: #00FFA3;');
    console.log('%cPowered by AI for smarter job applications', 'font-size: 14px; color: #B8C5E0;');
});
