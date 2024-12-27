document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');

    // Password visibility toggle
    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');

    if (togglePassword && passwordInput) {
        console.log('Toggle password button and password input found');

        togglePassword.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent form submission
            console.log('Toggle password button clicked');

            // Toggle the password visibility
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                this.querySelector('i').classList.remove('fa-eye');
                this.querySelector('i').classList.add('fa-eye-slash');
                console.log('Password visible');
            } else {
                passwordInput.type = 'password';
                this.querySelector('i').classList.remove('fa-eye-slash');
                this.querySelector('i').classList.add('fa-eye');
                console.log('Password hidden');
            }
        });
    } else {
        console.error('Elements not found:', {
            togglePassword: !!togglePassword,
            passwordInput: !!passwordInput
        });
    }
});
