/**
 * ConfirmDialog — modal confirmation for destructive actions.
 * Used by: All destructive actions across all phases.
 *
 * Requires explicit confirmation with named action button.
 * Returns Promise<boolean> — true if confirmed, false if cancelled.
 */
class ConfirmDialog {
  static _instance = null;

  static getInstance() {
    if (!ConfirmDialog._instance) {
      ConfirmDialog._instance = new ConfirmDialog();
    }
    return ConfirmDialog._instance;
  }

  constructor() {
    if (ConfirmDialog._instance) return ConfirmDialog._instance;
    this.el = null;
    this._pendingResolve = null;
    this._buildModal();
  }

  _buildModal() {
    this.el = document.createElement('div');
    this.el.className = 'modal fade confirm-dialog';
    this.el.setAttribute('tabindex', '-1');
    this.el.setAttribute('aria-labelledby', 'confirm-dialog-title');
    this.el.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content bg-dark border-secondary">
          <div class="modal-header border-secondary">
            <h5 class="modal-title" id="confirm-dialog-title">Confirm Action</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p id="confirm-dialog-message"></p>
          </div>
          <div class="modal-footer border-secondary">
            <button type="button" class="btn btn-secondary" id="confirm-dialog-cancel">Cancel</button>
            <button type="button" class="btn btn-danger" id="confirm-dialog-confirm">Confirm</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(this.el);
    this._bindEvents();
  }

  _bindEvents() {
    const cancelBtn = this.el.querySelector('#confirm-dialog-cancel');
    const confirmBtn = this.el.querySelector('#confirm-dialog-confirm');

    cancelBtn.addEventListener('click', () => {
      this._resolve(false);
      this._hide();
    });

    confirmBtn.addEventListener('click', () => {
      this._resolve(true);
      this._hide();
    });

    this.el.addEventListener('hidden.bs.modal', () => {
      if (this._pendingResolve) {
        this._resolve(false);
      }
    });
  }

  async show(options = {}) {
    const title = options.title || 'Confirm Action';
    const message = options.message || 'Are you sure?';
    const confirmText = options.confirmText || 'Confirm';
    const confirmClass = options.confirmClass || 'btn-danger';

    this.el.querySelector('#confirm-dialog-title').textContent = title;
    this.el.querySelector('#confirm-dialog-message').textContent = message;
    const confirmBtn = this.el.querySelector('#confirm-dialog-confirm');
    confirmBtn.textContent = confirmText;
    confirmBtn.className = 'btn ' + confirmClass;

    return new Promise(resolve => {
      this._pendingResolve = resolve;
      const modal = bootstrap.Modal.getOrCreateInstance(this.el);
      modal.show();
    });
  }

  _resolve(value) {
    if (this._pendingResolve) {
      this._pendingResolve(value);
      this._pendingResolve = null;
    }
  }

  _hide() {
    const modal = bootstrap.Modal.getInstance(this.el);
    if (modal) modal.hide();
  }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.ConfirmDialog = ConfirmDialog;
}
