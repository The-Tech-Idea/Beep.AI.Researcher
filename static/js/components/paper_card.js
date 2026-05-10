/**
 * PaperCard — reusable paper/recommendation card component.
 * Used by: Feed (P1), Knowledge Map side panel (P3), Search results (P6).
 *
 * Emits custom events: paper-card:save, paper-card:dismiss, paper-card:listen
 */
class PaperCard {
  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    this.data = options.data || {};
    this.compact = options.compact || false;
    this.showAbstract = options.showAbstract !== false && !this.compact;
    this.showActions = options.showActions !== false;
    this.onSave = options.onSave || null;
    this.onDismiss = options.onDismiss || null;
    this.onListen = options.onListen || null;
    this.onSaveToProject = options.onSaveToProject || null;

    this.el = null;
    this._render();
  }

  _render() {
    const d = this.data;
    const card = document.createElement('div');
    card.className = 'paper-card' + (this.compact ? ' paper-card--compact' : '');
    card.dataset.paperCardId = d.id || d.external_id || '';

    card.innerHTML = `
      <div class="paper-card__header">
        <span class="source-badge source-badge--${(d.source || '').replace('_', '-')}">${this._sourceLabel(d.source)}</span>
        <h4 class="paper-card__title">${this._esc(d.title || 'Untitled')}</h4>
      </div>
      ${!this.compact ? `
      <div class="paper-card__meta">
        ${d.authors && d.authors.length ? this._esc(d.authors.slice(0, 3).join(', ') + (d.authors.length > 3 ? ' et al.' : '')) : ''}
        ${d.publication_date ? ' · ' + this._esc(d.publication_date) : ''}
        ${d.doi ? ' · DOI: ' + this._esc(d.doi) : ''}
      </div>` : ''}
      ${this.showAbstract && d.abstract ? `
      <div class="paper-card__abstract">
        ${this._esc(d.abstract.length > 200 ? d.abstract.slice(0, 200) + '…' : d.abstract)}
        ${d.abstract.length > 200 ? '<button class="paper-card__expand" type="button">Expand</button>' : ''}
      </div>` : ''}
      ${d.reason ? `<span class="paper-card__reason">${this._esc(d.reason)}</span>` : ''}
      ${this.showActions ? `
      <div class="paper-card__actions">
        ${this.onSave ? `
        <div class="dropdown">
          <button class="btn btn-sm btn-outline-primary dropdown-toggle" type="button" data-bs-toggle="dropdown">Save</button>
          <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="#" data-action="save-reading-list">Save to Reading List</a></li>
            ${this.onSaveToProject ? '<li><a class="dropdown-item" href="#" data-action="save-to-project">Save to Project…</a></li>' : ''}
          </ul>
        </div>` : ''}
        ${this.onDismiss ? '<button class="btn btn-sm btn-outline-secondary" type="button" data-action="dismiss">Dismiss</button>' : ''}
        ${this.onListen ? '<button class="btn btn-sm btn-outline-info" type="button" data-action="listen"><i class="bi bi-volume-up"></i> Listen</button>' : ''}
      </div>` : ''}
    `;

    this.el = card;
    this._bindEvents();
    if (this.container) {
      this.container.appendChild(card);
    }
  }

  _bindEvents() {
    this.el.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.preventDefault();
        const action = btn.dataset.action;
        if (action === 'save-reading-list' && this.onSave) this.onSave(this.data);
        if (action === 'save-to-project' && this.onSaveToProject) this.onSaveToProject(this.data);
        if (action === 'dismiss' && this.onDismiss) this.onDismiss(this.data);
        if (action === 'listen' && this.onListen) this.onListen(this.data);
      });
    });

    const expandBtn = this.el.querySelector('.paper-card__expand');
    if (expandBtn) {
      expandBtn.addEventListener('click', () => {
        const abstractEl = this.el.querySelector('.paper-card__abstract');
        abstractEl.textContent = this.data.abstract;
        expandBtn.remove();
      });
    }
  }

  _sourceLabel(source) {
    const labels = {
      pubmed: 'PubMed',
      arxiv: 'arXiv',
      crossref: 'Crossref',
      semantic_scholar: 'S2',
    };
    return labels[source] || (source || '').replace('_', ' ');
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }

  getElement() { return this.el; }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.PaperCard = PaperCard;
}
