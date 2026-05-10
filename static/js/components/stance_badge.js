/**
 * StanceBadge — polarity label badge for evidence snippets.
 * Used by: Synthesis evidence table (P2), Citation Context (P6).
 *
 * Stances: supporting (green check), contradicting (red x), mentioning (grey dash).
 * Always includes icon + label — never relies on colour alone (WCAG AA).
 */
class StanceBadge {
  static STANCE_CONFIG = {
    supporting: { icon: 'bi-check-circle', color: 'var(--bs-success, #198754)', label: 'Supporting' },
    contradicting: { icon: 'bi-x-circle', color: 'var(--bs-danger, #dc3545)', label: 'Contradicting' },
    mentioning: { icon: 'bi-dash-circle', color: 'var(--bs-secondary-color, #adb5bd)', label: 'Mentioning' },
  };

  constructor(container, stance) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    this.stance = (stance || 'mentioning').toLowerCase();
    this.el = this._create();
    if (this.container) {
      this.container.appendChild(this.el);
    }
  }

  _create() {
    const config = StanceBadge.STANCE_CONFIG[this.stance] || StanceBadge.STANCE_CONFIG.mentioning;
    const span = document.createElement('span');
    span.className = 'stance-badge';
    span.setAttribute('role', 'status');
    span.setAttribute('aria-label', 'Evidence stance: ' + config.label);
    span.innerHTML = `<i class="bi ${config.icon}" aria-hidden="true"></i> ${config.label}`;
    span.style.cssText = `color:${config.color};font-weight:600;font-size:0.75rem;display:inline-flex;align-items:center;gap:0.25rem;`;
    return span;
  }

  getElement() { return this.el; }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.StanceBadge = StanceBadge;
}
