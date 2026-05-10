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

    const bindGenericConfirm = () => {
        document.querySelectorAll('form[data-admin-confirm]').forEach((form) => {
            form.addEventListener('submit', (event) => {
                const message = form.dataset.adminConfirm;
                if (message && !window.confirm(message)) {
                    event.preventDefault();
                }
            });
        });
    };

    const bindQuotaOverrideForms = () => {
        const userSelect = document.getElementById('quotaUserSelect');
        const userForm = document.getElementById('userQuotaOverrideForm');
        const userPlan = document.getElementById('quotaUserPlan');
        const userStorage = document.getElementById('quotaUserStorage');
        const userDocuments = document.getElementById('quotaUserDocuments');
        if (userSelect && userForm) {
            userSelect.addEventListener('change', () => {
                const option = userSelect.selectedOptions[0];
                userForm.action = userSelect.value ? `/admin/quota/users/${userSelect.value}/override` : '';
                if (userPlan) userPlan.value = option?.dataset.plan || '';
                if (userStorage) userStorage.value = option?.dataset.storage || '';
                if (userDocuments) userDocuments.value = option?.dataset.documents || '';
            });
            userForm.addEventListener('submit', (event) => {
                if (!userSelect.value) {
                    event.preventDefault();
                    window.alert('Choose a user.');
                }
            });
        }

        const tenantSelect = document.getElementById('quotaTenantSelect');
        const tenantForm = document.getElementById('tenantQuotaForm');
        const tenantPlan = document.getElementById('quotaTenantPlan');
        const tenantStorage = document.getElementById('quotaTenantStorage');
        const tenantDocuments = document.getElementById('quotaTenantDocuments');
        const tenantUpload = document.getElementById('quotaTenantUpload');
        if (tenantSelect && tenantForm) {
            tenantSelect.addEventListener('change', () => {
                const option = tenantSelect.selectedOptions[0];
                tenantForm.action = tenantSelect.value ? `/admin/quota/tenants/${tenantSelect.value}/save` : '';
                if (tenantPlan) tenantPlan.value = option?.dataset.plan || '';
                if (tenantStorage) tenantStorage.value = option?.dataset.storage || '';
                if (tenantDocuments) tenantDocuments.value = option?.dataset.documents || '';
                if (tenantUpload) tenantUpload.value = option?.dataset.upload || '';
            });
            tenantForm.addEventListener('submit', (event) => {
                if (!tenantSelect.value) {
                    event.preventDefault();
                    window.alert('Choose a tenant.');
                }
            });
        }
    };

    restoreActiveTab();
    bindTabPersistence();
    applyProgressWidths();
    bindDeleteConfirm();
    bindGenericConfirm();
    bindQuotaOverrideForms();
});
