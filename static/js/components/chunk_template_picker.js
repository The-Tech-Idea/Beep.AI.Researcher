/**
 * ChunkTemplatePicker — selector for RAG chunk templates.
 * Used by: Collection setup (P1/2/3), Settings chunk template management (§9.10).
 *
 * Shows system built-in templates (read-only, prefixed system-) and user-owned templates.
 * Supports cloning, creating, editing, and applying templates.
 */
class ChunkTemplatePicker {
  static STRATEGY_DESCRIPTIONS = {
    sentence: 'Split text at sentence boundaries. Simple and predictable.',
    recursive: 'Recursively split by separators (paragraphs → sentences → words).',
    semantic: 'Use embedding similarity to detect topic shifts. Best for research papers.',
    parent_child: 'Small child chunks for precise retrieval + parent chunks for context.',
    markdown_heading: 'Split at markdown heading boundaries. Preserves code blocks and tables.',
    graph_rag: 'Entity extraction + Leiden community detection. Best for ≥20 papers.',
    raptor: 'Recursive tree-based summarisation for hierarchical documents.',
    proposition: 'Extract atomic propositions for precise fact-level retrieval.',
    agentic: 'LLM-driven chunking. Highest quality but slowest.',
  };

  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    this.templates = options.templates || [];
    this.selectedId = options.selectedId || null;
    this.onSelect = options.onSelect || null;
    this.el = this._create();
    if (this.container) {
      this.container.appendChild(this.el);
    }
  }

  _create() {
    const wrapper = document.createElement('div');
    wrapper.className = 'chunk-template-picker';

    const label = document.createElement('label');
    label.className = 'form-label';
    label.textContent = 'Chunk Template';
    wrapper.appendChild(label);

    const select = document.createElement('select');
    select.className = 'form-select';
    select.innerHTML = '<option value="">— Select a template —</option>';

    const systemTemplates = this.templates.filter(t => t.slug && t.slug.startsWith('system-'));
    const userTemplates = this.templates.filter(t => !t.slug || !t.slug.startsWith('system-'));

    if (systemTemplates.length) {
      const optGroup = document.createElement('optgroup');
      optGroup.label = 'Built-in';
      systemTemplates.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = `${t.name} (${t.strategy})`;
        opt.dataset.strategy = t.strategy;
        opt.disabled = t.is_builtin;
        if (t.id === this.selectedId) opt.selected = true;
        optGroup.appendChild(opt);
      });
      select.appendChild(optGroup);
    }

    if (userTemplates.length) {
      const optGroup = document.createElement('optgroup');
      optGroup.label = 'My Templates';
      userTemplates.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.name;
        opt.dataset.strategy = t.strategy;
        if (t.id === this.selectedId) opt.selected = true;
        optGroup.appendChild(opt);
      });
      select.appendChild(optGroup);
    }

    wrapper.appendChild(select);

    const desc = document.createElement('div');
    desc.className = 'chunk-template-picker__desc mt-2 small text-muted';
    desc.id = 'chunk-template-desc';
    wrapper.appendChild(desc);

    select.addEventListener('change', () => {
      const selected = select.selectedOptions[0];
      if (selected && selected.dataset.strategy) {
        desc.textContent = ChunkTemplatePicker.STRATEGY_DESCRIPTIONS[selected.dataset.strategy] || '';
      } else {
        desc.textContent = '';
      }
      if (this.onSelect) {
        this.onSelect(select.value);
      }
    });

    select.dispatchEvent(new Event('change'));

    return wrapper;
  }

  getValue() {
    return this.el.querySelector('select').value;
  }

  getElement() { return this.el; }
}

if (window.BEEP_COMPONENTS) {
  window.BEEP_COMPONENTS.ChunkTemplatePicker = ChunkTemplatePicker;
}
