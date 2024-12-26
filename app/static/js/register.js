document.addEventListener('DOMContentLoaded', function() {
    // Form submission handling
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            const flipContainer = document.querySelector('.flip-container');
            if (flipContainer) {
                flipContainer.classList.add('flipped');
            }
        });
    }
});