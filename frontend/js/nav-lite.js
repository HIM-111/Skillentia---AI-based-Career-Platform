document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    const navbar = document.querySelector('.navbar');

    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', function() {
            const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
            menuToggle.setAttribute('aria-expanded', String(!isExpanded));
            navLinks.classList.toggle('active');
        });

        navLinks.querySelectorAll('a').forEach((link) => {
            link.addEventListener('click', function() {
                navLinks.classList.remove('active');
                menuToggle.setAttribute('aria-expanded', 'false');
            });
        });
    }

    if (navbar) {
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 100) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }
});
