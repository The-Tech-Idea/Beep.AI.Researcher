/**
 * ToastNotification — global toast for success/error/warning feedback.
 * Used by: All phases for action confirmation.
 *
 * Usage: ToastNotification.success('Saved!') or ToastNotification.error('Failed to save')
 * Auto-dismisses after configurable duration (default 3s for success, 5s for error).
 */
class ToastNotification {
  static _container = null;

  static _getContainer() {
    if (!ToastNotification._container) {
      ToastNotification._container = document.createElement('div');
      ToastNotification._container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
      ToastNotification._container.style.cssText = 'z-index: 9999;';
      document.body.appendChild(ToastNotification._container);
    }
    return ToastNotification._container;
  }

  static show(message, type = 'info', duration = 3000) {
    const container = ToastNotification._getContainer();
    const toastEl = document.createElement('div');
    const bsClass = `bg-${type === 'error' ? 'danger' : type}`;

    const icons = {
      success: 'bi-check-circle',
      error: 'bi-x-circle',
      warning: 'bi-exclamation-triangle',
      info: 'bi-info-circle',
    };

    toastEl.className = `toast align-items-center text-white ${bsClass} border-0 mb-2`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi ${icons[type] || icons.info} me-1"></i> ${ToastNotification._esc(message)}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: duration });
    toast.show();

    toastEl.addEventListener('hidden.bs.toast', () => {
      toastEl.remove();
    });

    return toastEl;
  }

  static success(message, duration = 3000) {
    return ToastNotification.show(message, 'success', duration);
  }

  static error(message, duration = 5000) {
    return ToastNotification.show(message, 'error', duration);
  }

  static warning(message, duration = 4000) {
    return ToastNotification.show(message, 'warning', duration);
  }

  static info(message, duration = 3000) {
    return ToastNotification.show(message, 'info', duration);
  }

  static _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.ToastNotification = ToastNotification;
}
