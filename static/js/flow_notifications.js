/* Flow helpers: toasts, loading state, and inline statuses. */
(function () {
    'use strict';

    function normalizeVariant(variant) {
        switch (String(variant || 'info').trim().toLowerCase()) {
            case 'success':
                return 'success';
            case 'warning':
            case 'warn':
                return 'warning';
            case 'danger':
            case 'error':
                return 'danger';
            default:
                return 'info';
        }
    }

    function getConsoleMethod(variant) {
        switch (normalizeVariant(variant)) {
            case 'danger':
                return 'error';
            case 'warning':
                return 'warn';
            default:
                return 'info';
        }
    }

    function normalizeOptions(options) {
        if (typeof options === 'string') {
            return { variant: options };
        }

        return options || {};
    }

    function ensureToastContainer() {
        if (!document.body) {
            return null;
        }

        var container = document.getElementById('flowToastContainer');
        if (container) {
            return container;
        }

        container = document.createElement('div');
        container.id = 'flowToastContainer';
        container.className = 'flow-toast-stack';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(container);
        return container;
    }

    function showToast(message, options = {}) {
        if (!message) {
            return null;
        }

        const container = ensureToastContainer();
        if (!container) {
            return null;
        }

        const normalized = normalizeOptions(options);
        const variant = normalizeVariant(normalized.variant);
        const duration = Number(normalized.duration) || 4200;
        const toast = document.createElement('div');
        toast.className = `flow-toast flow-toast-${variant}`;
        toast.textContent = message;
        container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('flow-toast-show'));
        setTimeout(() => {
            toast.classList.remove('flow-toast-show');
            toast.addEventListener('transitionend', () => toast.remove(), { once: true });
        }, duration);
        return toast;
    }

    function notify(message, options = {}) {
        if (!message) {
            return null;
        }

        const normalized = normalizeOptions(options);
        const toast = showToast(message, normalized);
        if (toast) {
            return toast;
        }

        console[getConsoleMethod(normalized.variant)](message);
        return null;
    }

    function setButtonLoading(button, loading, options = {}) {
        if (!button) {
            return;
        }

        const normalized = normalizeOptions(options);

        if (loading) {
            if (button.dataset.flowLoading === 'true') {
                return;
            }

            button.dataset.flowLoading = 'true';
            if (!button._flowOriginalChildren) {
                button._flowOriginalChildren = Array.from(button.childNodes).map((node) => node.cloneNode(true));
            }
            if (!button.dataset.flowDefaultLabel) {
                button.dataset.flowDefaultLabel = (button.textContent || '').trim();
            }

            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            const spinner = document.createElement('span');
            spinner.className = 'flow-spinner';
            spinner.setAttribute('aria-hidden', 'true');
            const label = document.createElement('span');
            label.className = 'flow-button-loading-label';
            label.textContent = normalized.loadingLabel || button.dataset.flowDefaultLabel || 'Loading...';
            button.replaceChildren(spinner, label);
            return;
        }

        button.dataset.flowLoading = 'false';
        button.disabled = false;
        button.removeAttribute('aria-busy');
        if (button._flowOriginalChildren) {
            button.replaceChildren();
            button._flowOriginalChildren.forEach((node) => {
                button.appendChild(node.cloneNode(true));
            });
        }
    }

    function setFlowStatus(node, text, variant = 'info') {
        if (!node) {
            return;
        }

        node.textContent = text || '';
        node.dataset.flowVariant = normalizeVariant(variant);

        node.classList.add('flow-status');
        node.classList.remove('flow-status-info', 'flow-status-warning', 'flow-status-success', 'flow-status-danger');
        node.classList.add(`flow-status-${normalizeVariant(variant)}`);
    }

    window.beepUI = window.beepUI || {};
    window.beepUI.notify = notify;
    window.beepUI.showToast = showToast;
    window.beepUI.setButtonLoading = setButtonLoading;
    window.beepUI.toggleButtonLoading = setButtonLoading;
    window.beepUI.setFlowStatus = setFlowStatus;
})();
