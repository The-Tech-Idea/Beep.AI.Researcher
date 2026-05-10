/**
 * SourceBadge — source identifier badge (PubMed, arXiv, Crossref, S2).
 * Used by: Feed (P1), References (P6).
 */
class SourceBadge {
  static SOURCE_COLORS = {
    pubmed: '#3b82f6',
    arxiv: '#f59e0b',
    crossref: '#10b981',
    semantic_scholar: '#8b5cf6',
  };

  constructor(container, source) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    this.source = source;
    this.el = this._create();
    if (this.container) {
      this.container.appendChild(this.el);
    }
  }

  _create() {
    const span = document.createElement('span');
    span.className = 'source-badge';
    const color = SourceBadge.SOURCE_COLORS[this.source] || '#6b7280';
    span.style.cssText = `background:${color};color:#fff;font-size:0.7rem;padding:0.1rem 0.4rem;border-radius:0.25rem;font-weight:600;text-transform:uppercase;`;
    span.textContent = this._label();
    return span;
  }

  _label() {
    const labels = {
      pubmed: 'PubMed',
      arxiv: 'arXiv',
      crossref: 'Crossref',
      semantic_scholar: 'S2',
    };
    return labels[this.source] || (this.source || '').replace('_', ' ');
  }

  getElement() { return this.el; }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.SourceBadge = SourceBadge;
}
