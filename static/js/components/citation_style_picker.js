/**
 * CitationStylePicker — searchable dropdown for 50+ CSL citation styles.
 * Used by: Synthesis export (P2), Writing Studio (P4), Citation Intelligence (P6).
 *
 * Supports: style search, format selection (HTML, plain text, BibTeX, RIS, DOCX).
 * Emits custom event: citation-style:export
 */
class CitationStylePicker {
  static DEFAULT_STYLES = [
    { id: 'apa', name: 'APA 7th', group: 'Social Sciences' },
    { id: 'mla', name: 'MLA 9th', group: 'Humanities' },
    { id: 'chicago', name: 'Chicago 17th', group: 'History' },
    { id: 'harvard', name: 'Harvard', group: 'General' },
    { id: 'ieee', name: 'IEEE', group: 'Engineering' },
    { id: 'vancouver', name: 'Vancouver', group: 'Medicine' },
    { id: 'nature', name: 'Nature', group: 'Journals' },
    { id: 'cell', name: 'Cell', group: 'Journals' },
    { id: 'jama', name: 'JAMA', group: 'Medicine' },
    { id: 'ama', name: 'AMA', group: 'Medicine' },
  ];

  static OUTPUT_FORMATS = [
    { id: 'html', name: 'Formatted Text (HTML)' },
    { id: 'text', name: 'Plain Text' },
    { id: 'bibtex', name: 'BibTeX' },
    { id: 'ris', name: 'RIS' },
    { id: 'docx', name: 'Word (DOCX)' },
  ];

  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    this.styles = options.styles || CitationStylePicker.DEFAULT_STYLES;
    this.onExport = options.onExport || null;

    this.el = this._create();
    if (this.container) {
      this.container.appendChild(this.el);
    }
  }

  _create() {
    const wrapper = document.createElement('div');
    wrapper.className = 'citation-style-picker';

    // Style selector
    const styleGroup = document.createElement('div');
    styleGroup.className = 'mb-2';
    styleGroup.innerHTML = `
      <label class="form-label small">Citation Style</label>
      <input type="text" class="form-control form-control-sm citation-style-picker__search" placeholder="Search styles…" autocomplete="off">
      <select class="form-select form-select-sm mt-1 citation-style-picker__style" size="6">
        ${this._renderStyleOptions()}
      </select>
    `;
    wrapper.appendChild(styleGroup);

    // Output format selector
    const formatGroup = document.createElement('div');
    formatGroup.className = 'mb-2';
    formatGroup.innerHTML = `
      <label class="form-label small">Output Format</label>
      <select class="form-select form-select-sm citation-style-picker__format">
        ${CitationStylePicker.OUTPUT_FORMATS.map(f => `<option value="${f.id}">${f.name}</option>`).join('')}
      </select>
    `;
    wrapper.appendChild(formatGroup);

    // Export button
    const exportBtn = document.createElement('button');
    exportBtn.className = 'btn btn-sm btn-primary w-100 citation-style-picker__export';
    exportBtn.type = 'button';
    exportBtn.textContent = 'Export';
    wrapper.appendChild(exportBtn);

    // Search filter
    const searchInput = styleGroup.querySelector('.citation-style-picker__search');
    const selectEl = styleGroup.querySelector('.citation-style-picker__style');
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase();
      selectEl.querySelectorAll('option').forEach(opt => {
        opt.hidden = !opt.textContent.toLowerCase().includes(query);
      });
    });

    // Export action
    exportBtn.addEventListener('click', () => {
      const style = selectEl.value;
      const format = formatGroup.querySelector('.citation-style-picker__format').value;
      if (this.onExport) {
        this.onExport({ style, format });
      }
      this.el.dispatchEvent(new CustomEvent('citation-style:export', {
        detail: { style, format },
      }));
    });

    return wrapper;
  }

  _renderStyleOptions() {
    const grouped = {};
    this.styles.forEach(s => {
      const group = s.group || 'Other';
      if (!grouped[group]) grouped[group] = [];
      grouped[group].push(s);
    });

    let html = '';
    for (const [group, styles] of Object.entries(grouped)) {
      html += `<optgroup label="${group}">`;
      styles.forEach(s => {
        html += `<option value="${s.id}">${s.name}</option>`;
      });
      html += '</optgroup>';
    }
    return html;
  }

  getElement() { return this.el; }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.CitationStylePicker = CitationStylePicker;
}
