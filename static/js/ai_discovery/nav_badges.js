'use strict';

(function () {
    const badge = document.getElementById('alerts-nav-count');
    if (!badge) return;

    function setAlertsCount(count) {
        const numericCount = Number.isFinite(Number(count)) ? Math.max(0, Number(count)) : 0;
        if (!numericCount) {
            badge.textContent = '';
            badge.classList.add('d-none');
            return;
        }

        badge.textContent = numericCount > 99 ? '99+' : String(numericCount);
        badge.classList.remove('d-none');
    }

    async function refreshAlertsCount() {
        try {
            const response = await fetch('/alerts/count', {
                headers: { 'X-Requested-With': 'SPA' },
            });
            if (!response.ok) {
                setAlertsCount(0);
                return;
            }

            const data = await response.json();
            setAlertsCount(data.count || 0);
        } catch (_) {
            setAlertsCount(0);
        }
    }

    window.aiDiscoveryNav = Object.assign(window.aiDiscoveryNav || {}, {
        refreshAlertsCount,
        setAlertsCount,
    });

    document.addEventListener('ai-discovery:alerts-count-changed', function (event) {
        if (typeof event.detail?.count === 'number') {
            setAlertsCount(event.detail.count);
        } else {
            refreshAlertsCount();
        }
    });

    refreshAlertsCount();
}());