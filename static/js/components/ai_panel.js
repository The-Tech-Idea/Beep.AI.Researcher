/**
 * AIPanel — collapsible AI-powered panel for hub pages.
 * Used by: Document detail panels (P1/P4/P6), all hub injections.
 *
 * Features lazy loading: content is fetched via AJAX only when the user opens the panel.
 * Emits custom events: ai-panel:open, ai-panel:close, ai-panel:loaded
 */
class AIPanel {
  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    this.panelName = options.panelName || 'unknown';
    this.endpoint = options.endpoint || '';
    this.title = options.title || '';
    this.icon = options.icon || 'bi-stars';
    this.lazy = options.lazy !== false;
    this.loaded = false;
    this.loading = false;

    this.el = this._create();
    if (this.container) {
      this.container.appendChild(this.el);
    }
    this._bindEvents();
  }

  _create() {
    const details = document.createElement('details');
    details.className = 'ai-panel';
    details.dataset.panel = this.panelName;

    details.innerHTML = `
      <summary class="ai-panel__summary">
        <i class="bi ${this.icon}" aria-hidden="true"></i>
        <span>${this._esc(this.title)}</span>
        <span class="ai-panel__spinner spinner-border spinner-border-sm ms-auto d-none" role="status"></span>
      </summary>
      <div class="ai-panel__content">
        <div class="ai-panel__placeholder">
          <div class="spinner-border text-secondary" role="status"></div>
          <span class="ms-2">Loading…</span>
        </div>
      </div>
    `;

    return details;
  }

  _bindEvents() {
    this.el.addEventListener('toggle', () => {
      if (this.el.open && this.lazy && !this.loaded && !this.loading) {
        this._load();
      }
    });
  }

  async _load() {
    if (!this.endpoint) return;
    this.loading = true;
    const spinner = this.el.querySelector('.ai-panel__spinner');
    spinner.classList.remove('d-none');

    try {
      const resp = await fetch(this.endpoint);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      this._renderContent(data);
      this.loaded = true;

      this.el.dispatchEvent(new CustomEvent('ai-panel:loaded', { detail: { panel: this.panelName, data } }));
    } catch (err) {
      this._renderError(err.message);
    } finally {
      this.loading = false;
      spinner.classList.add('d-none');
    }
  }

  _renderContent(data) {
    const contentEl = this.el.querySelector('.ai-panel__content');
    if (typeof data === 'string') {
      contentEl.innerHTML = data;
    } else if (typeof data.html === 'string') {
      contentEl.innerHTML = data.html;
    } else {
      contentEl.innerHTML = `<pre class="text-muted">${this._esc(JSON.stringify(data, null, 2))}</pre>`;
    }
  }

  _renderError(message) {
    const contentEl = this.el.querySelector('.ai-panel__content');
    contentEl.innerHTML = `
      <div class="alert alert-warning">
        <i class="bi bi-exclamation-triangle"></i>
        Failed to load content. <button class="btn btn-sm btn-link p-0 ai-panel__retry">Retry</button>
      </div>
    `;
    contentEl.querySelector('.ai-panel__retry').addEventListener('click', () => {
      this.loaded = false;
      this._load();
    });
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }

  getElement() { return this.el; }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.AIPanel = AIPanel;
}
