# Design System Master File

> Source of truth aligned with AI Server branding.
> Page-specific overrides in `design-system/pages/*.md` take precedence.

---

**Project:** Beep.AI.Researcher  
**Updated:** 2026-02-25  
**Theme:** AI Server Indigo/Purple Gradient

---

## Global Tokens

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary Indigo | `#6366f1` | `--color-primary` |
| Accent Purple | `#a855f7` | `--color-secondary` |
| Accent Fuchsia | `#d946ef` | `--color-accent` |
| Active Link (Light) | `#4f46e5` | `--color-primary-hover` |
| Active Link (Dark) | `#818cf8` | (dark override) |
| Success | `#22c55e` | `--color-success` |
| Danger | `#ef4444` | `--color-error` |
| Info | `#6366f1` | `--color-info` |
| Warning | `#ffc107` | `--color-warning` |

**Primary Gradient:** `linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #d946ef 100%)`

### Background + Text

| Token | Light | Dark |
|------|-------|------|
| `--bg-primary` | `#f8fafc` | `#030305` |
| `--bg-surface` | `rgba(255,255,255,0.7)` | `rgba(18,18,28,0.7)` |
| `--bg-tertiary` | `#f1f5f9` | `#0a0a12` |
| `--text-primary` | `#0f172a` | `#e2e8f0` |
| `--text-secondary` | `#475569` | `rgba(255,255,255,0.6)` |
| `--border-color` | `rgba(15,23,42,0.12)` | `rgba(255,255,255,0.08)` |

### Typography

- **Headings:** `'Outfit', 'Noto Sans Arabic', sans-serif`
- **Body/UI:** `'Inter', 'Noto Sans Arabic', sans-serif`
- **Monospace:** `'JetBrains Mono', monospace`

### Layout Tokens

| Token | Value |
|------|-------|
| `--sidebar-width` | `280px` |
| `--header-height` | `70px` |
| `--border-radius-lg` | `16px` |
| `--border-radius-md` | `12px` |
| `--border-radius-sm` | `8px` |
| `--backdrop-blur` | `blur(20px)` |

---

## Accessibility + i18n Rules

- Always set dynamic HTML attributes: `lang` from locale and `dir="rtl"` for Arabic.
- Include `Noto Sans Arabic` in font stacks.
- Use explicit form label associations (`for` + `id`).
- Icon-only buttons must include `aria-label`.
- Add `aria-current="page"` to active navigation links.
- Preserve visible focus states and support keyboard navigation.

---

## Component Guidance

- Keep shared component overrides in `static/css/design-system.css`.
- Avoid redefining `.btn-primary`, `.card`, and `.form-control` in feature-specific CSS files.
- Load heavy libraries (like Chart.js) only on pages that use them.
- Use app-version cache keys (stable), not random request-time cache busters.

---

## Anti-Patterns

- ❌ Hardcoded `<html lang="en">` when locale-aware rendering is available.
- ❌ Random cache-busting values on every request.
- ❌ Global chart library imports on unrelated pages.
- ❌ Hover-only affordances for touch interactions.
