document.addEventListener('DOMContentLoaded', function() {
    // Mobile Navigation
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function(e) {
            e.preventDefault();
            this.classList.toggle('active');
            navMenu.classList.toggle('show');
        });

        // Close menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!navMenu.contains(e.target) && !navToggle.contains(e.target)) {
                navMenu.classList.remove('show');
                navToggle.classList.remove('active');
            }
        });

        // Handle window resize
        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                navMenu.classList.remove('show');
                navToggle.classList.remove('active');
            }
        });
    }

    // Handle dropdowns for both mobile and desktop
    const dropdowns = document.querySelectorAll('.dropdown-toggle');
    dropdowns.forEach(dropdown => {
        const parentItem = dropdown.parentElement;
        const menu = dropdown.nextElementSibling;

        // Touch event handling
        dropdown.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const wasOpen = parentItem.classList.contains('show');

            // Close all other dropdowns
            dropdowns.forEach(other => {
                const otherParent = other.parentElement;
                if (otherParent !== parentItem) {
                    otherParent.classList.remove('show');
                    const otherMenu = other.nextElementSibling;
                    if (otherMenu) otherMenu.classList.remove('show');
                }
            });

            // Toggle current dropdown
            if (!wasOpen) {
                parentItem.classList.add('show');
                if (menu) menu.classList.add('show');
            } else {
                parentItem.classList.remove('show');
                if (menu) menu.classList.remove('show');
            }
        });

        // Mouse events for desktop
        if (window.innerWidth >= 768) {
            parentItem.addEventListener('mouseenter', function() {
                if (!('ontouchstart' in window)) {
                    this.classList.add('show');
                    if (menu) menu.classList.add('show');
                }
            });

            parentItem.addEventListener('mouseleave', function() {
                if (!('ontouchstart' in window)) {
                    this.classList.remove('show');
                    if (menu) menu.classList.remove('show');
                }
            });
        }

        // Click handling for mobile
        dropdown.addEventListener('click', function(e) {
            if (window.innerWidth < 768) {
                e.preventDefault();
                e.stopPropagation();
                
                const wasOpen = parentItem.classList.contains('show');

                // Close all other dropdowns
                dropdowns.forEach(other => {
                    const otherParent = other.parentElement;
                    if (otherParent !== parentItem) {
                        otherParent.classList.remove('show');
                        const otherMenu = other.nextElementSibling;
                        if (otherMenu) otherMenu.classList.remove('show');
                    }
                });

                // Toggle current dropdown
                parentItem.classList.toggle('show');
                if (menu) menu.classList.toggle('show');
            }
        });
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            dropdowns.forEach(dropdown => {
                const parentItem = dropdown.parentElement;
                const menu = dropdown.nextElementSibling;
                parentItem.classList.remove('show');
                if (menu) menu.classList.remove('show');
            });
        }
    });

    // Toast notification function
    window.showToast = function(message, type = 'success') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            console.error('Toast container not found');
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    };

    // Handle keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // Close all dropdowns
            dropdowns.forEach(dropdown => {
                const parentItem = dropdown.parentElement;
                const menu = dropdown.nextElementSibling;
                parentItem.classList.remove('show');
                if (menu) menu.classList.remove('show');
            });
            // Close mobile menu
            if (navMenu) {
                navMenu.classList.remove('show');
                if (navToggle) navToggle.classList.remove('active');
            }
        }
    });
});
