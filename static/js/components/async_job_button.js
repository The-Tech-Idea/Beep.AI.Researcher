/**
 * AsyncJobButton — button that manages long-running AI task states.
 * Used by: Feed refresh, Synthesis generate, Extract, Flashcards, Knowledge Map build.
 *
 * States: idle → loading → complete → reset (after delay)
 * Minimum 300ms loading display to avoid flicker.
 * Emits custom events: async-job:start, async-job:complete, async-job:error
 */
class AsyncJobButton {
  constructor(button, options = {}) {
    this.button = typeof button === 'string'
      ? document.querySelector(button)
      : button;
    this.loadingText = options.loadingText || 'Processing…';
    this.completeText = options.completeText || 'Done!';
    this.completeDuration = options.completeDuration || 2000;
    this.minLoadingMs = options.minLoadingMs || 300;
    this.running = false;

    this._originalText = this.button.textContent.trim();
    this._originalDisabled = this.button.disabled;
    this._bindEvents();
  }

  _bindEvents() {
    if (!this.button.dataset.asyncBound) {
      this.button.dataset.asyncBound = 'true';
      this.button.addEventListener('click', e => {
        if (this.running) {
          e.preventDefault();
          return;
        }
        this.start();
      });
    }
  }

  start() {
    if (this.running) return;
    this.running = true;
    this._setState('loading');
    this.button.dispatchEvent(new CustomEvent('async-job:start'));
  }

  async run(fn) {
    this.start();
    const startTime = Date.now();
    try {
      const result = await fn();
      const elapsed = Date.now() - startTime;
      if (elapsed < this.minLoadingMs) {
        await new Promise(r => setTimeout(r, this.minLoadingMs - elapsed));
      }
      this.complete(result);
      return result;
    } catch (err) {
      this.error(err);
      throw err;
    }
  }

  complete(result) {
    this._setState('complete');
    this.button.dispatchEvent(new CustomEvent('async-job:complete', { detail: result }));
    setTimeout(() => this.reset(), this.completeDuration);
  }

  error(err) {
    this._setState('error', err.message || 'Failed');
    this.button.dispatchEvent(new CustomEvent('async-job:error', { detail: err }));
    setTimeout(() => this.reset(), 3000);
  }

  reset() {
    this.running = false;
    this.button.textContent = this._originalText;
    this.button.disabled = this._originalDisabled;
    this.button.classList.remove('btn-loading', 'btn-complete', 'btn-error');
  }

  _setState(state, message) {
    this.button.classList.remove('btn-loading', 'btn-complete', 'btn-error');

    switch (state) {
      case 'loading':
        this.button.disabled = true;
        this.button.textContent = this.loadingText;
        this.button.classList.add('btn-loading');
        break;
      case 'complete':
        this.button.textContent = this.completeText;
        this.button.classList.add('btn-complete');
        break;
      case 'error':
        this.button.textContent = message || 'Error';
        this.button.classList.add('btn-error');
        this.button.disabled = false;
        break;
    }
  }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.AsyncJobButton = AsyncJobButton;
}
