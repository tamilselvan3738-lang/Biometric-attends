document.addEventListener('DOMContentLoaded', () => {
    // Mobile Sidebar Toggle
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('active');
        });
    }

    // Auto-dismiss alert messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            let bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // Global Password Visibility Toggle Injection
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        if (input.dataset.passwordToggle === 'true') return;
        input.dataset.passwordToggle = 'true';

        const parent = input.parentElement;
        if (parent) {
            let container = parent;
            const hasLabel = parent.querySelector('label');
            const isLoginCustom = parent.classList.contains('form-group-custom');

            if (hasLabel && !isLoginCustom) {
                const wrapper = document.createElement('div');
                wrapper.className = 'position-relative w-100';
                input.parentNode.insertBefore(wrapper, input);
                wrapper.appendChild(input);
                container = wrapper;
            } else {
                const origPosition = window.getComputedStyle(parent).position;
                if (origPosition !== 'relative' && origPosition !== 'absolute' && origPosition !== 'fixed') {
                    parent.style.position = 'relative';
                }
            }

            input.style.paddingRight = '2.75rem';

            const toggleButton = document.createElement('button');
            toggleButton.type = 'button';
            toggleButton.className = 'btn btn-link text-secondary position-absolute end-0 top-50 translate-middle-y me-2 text-decoration-none shadow-none p-0';
            toggleButton.style.zIndex = '10';
            toggleButton.style.border = 'none';
            toggleButton.style.background = 'transparent';
            toggleButton.style.boxShadow = 'none';
            
            const eyeIcon = document.createElement('i');
            eyeIcon.className = 'fas fa-eye';
            eyeIcon.style.fontSize = '1.05rem';
            eyeIcon.style.opacity = '0.7';
            toggleButton.appendChild(eyeIcon);
            
            container.appendChild(toggleButton);

            toggleButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (input.type === 'password') {
                    input.type = 'text';
                    eyeIcon.className = 'fas fa-eye-slash';
                } else {
                    input.type = 'password';
                    eyeIcon.className = 'fas fa-eye';
                }
            });
        }
    });
});
