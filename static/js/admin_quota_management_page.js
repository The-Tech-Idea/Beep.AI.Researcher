'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const configNode = document.getElementById('admin-quota-config');
    if (!configNode) {
        return;
    }

    const config = JSON.parse(configNode.textContent);

    const restoreActiveTab = () => {
        const storedTab = window.sessionStorage.getItem(config.storageQuotaTabKey);
        if (!storedTab) {
            return;
        }

        const tabButton = document.querySelector(`#quotaTabs button[data-bs-target="${storedTab}"]`);
        if (tabButton) {
            window.bootstrap.Tab.getOrCreateInstance(tabButton).show();
        }
    };

    const bindTabPersistence = () => {
        document.querySelectorAll('#quotaTabs button[data-bs-toggle="tab"]').forEach((button) => {
            button.addEventListener('shown.bs.tab', (event) => {
                window.sessionStorage.setItem(config.storageQuotaTabKey, event.target.dataset.bsTarget);
            });
        });
    };

    const applyProgressWidths = () => {
        document.querySelectorAll('.admin-quota-progress-bar[data-pct]').forEach((bar) => {
            bar.style.setProperty('--quota-progress-width', `${bar.dataset.pct}%`);
        });
    };

    const bindDeleteConfirm = () => {
        document.querySelectorAll('.admin-quota-tier-delete-form').forEach((form) => {
            form.addEventListener('submit', (event) => {
                const tierName = form.dataset.tierName || '';
                const confirmed = window.confirm(
                    `${config.deleteTierConfirmPrefix}${tierName}${config.deleteTierConfirmSuffix}`
                );
                if (!confirmed) {
                    event.preventDefault();
                }
            });
        });
    };

    restoreActiveTab();
    bindTabPersistence();
    applyProgressWidths();
    bindDeleteConfirm();
});
