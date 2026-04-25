/**
 * Project Sidebar Interactions
 */
(function() {
    'use strict';
    
    const sidebar = document.getElementById('workspaceSidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    
    if (!sidebar || !toggleBtn) return;
    
    // Load saved state
    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (isCollapsed && window.innerWidth > 1024) {
        sidebar.classList.add('collapsed');
    }
    
    // Toggle sidebar
    toggleBtn.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });
    
    // Mobile: close sidebar when clicking outside
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 768) {
            if (sidebar.classList.contains('open') && 
                !sidebar.contains(e.target) && 
                !e.target.closest('.mobile-menu-btn')) {
                sidebar.classList.remove('open');
            }
        }
    });
    
    // Mobile menu button (if exists in navbar)
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', function() {
            // Prevent overlap with the global SPA sidebar on mobile.
            document.getElementById('spa-sidebar')?.classList.remove('mobile-open');
            sidebar.classList.toggle('open');
        });
    }
    
    // Handle resize
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            if (window.innerWidth > 768) {
                sidebar.classList.remove('open');
            }
            if (window.innerWidth > 1024) {
                const savedState = localStorage.getItem('sidebarCollapsed') === 'true';
                sidebar.classList.toggle('collapsed', savedState);
            }
        }, 100);
    });
})();
