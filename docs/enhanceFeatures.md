# Beep.AI.Researcher — Full Feature Enhancement Plan

> **Date:** 2026-02-25  
> **Audience:** Non-technical users (researchers, students, academics)  
> **Goal:** Make every feature self-explanatory, clearly connected to other features, and usable without any technical knowledge  
> **Scope:** All 18 project-level features across the sidebar  

---

## The Core Problem

Every page in the app currently behaves as an **island**. A user who uploads documents has no idea that the same documents power the AI chat, the coding tool, the extraction table, and the report writer. A user who creates codes has no idea they appear in the Matrix or can be inserted into a Report. There is **no visible workflow** — just a list of menu items.

The solution is not to add more text. It is to **build the connections into the UI itself** — badges, cross-links, "used in" indicators, "next step" prompts, and consistent document references everywhere.

---

## The Research Workflow (The Mental Model Users Need)

Every feature maps to a step in a natural research process. This workflow should be visible on the Overview page and subtly reinforced on every other page:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    YOUR RESEARCH WORKFLOW                               │
│                                                                         │
│  1. UPLOAD     →  2. READ & ASK  →  3. ORGANISE   →  4. ANALYSE        │
│  Documents        Ask AI             Code themes       Extract data     │
│                   Find answers        Tag excerpts      Run statistics  │
│                                                                         │
│  5. VERIFY     →  6. WRITE       →  7. STUDY       →  8. MANAGE        │
│  Contradictions   Report             Flashcards        Tasks            │
│  AI Audit         Share & Export     Quizzes           Retention        │
└─────────────────────────────────────────────────────────────────────────┘
```

This workflow diagram should render as a visual "pipeline" on the **Overview page** and in a collapsible "How does this fit in?" section on every feature page.

---

## Feature Inventory — Plain Language Descriptions

| Page | What it does (plain language) | Currently connected to |
|------|------------------------------|----------------------|
| **Overview** | Your project dashboard. Shows counts, quick-links, and recent activity | All pages |
| **Documents** | Upload and manage your research papers, PDFs, spreadsheets | All features |
| **Ask AI** | Chat with your documents — ask questions, get answers with source quotes | Documents |
| **Codes** | Label and tag important themes or categories across your documents | Documents, Matrix, Report |
| **Coding Matrix** | See a table showing which codes appear in which documents | Codes, Documents |
| **Extraction** | Pull specific data fields from all your documents into one table | Documents, Stats, Report |
| **Tasks** | Kanban to-do board to track your research steps | Nothing (isolated) |
| **Report** | Write your research report with AI assistance | Codes, Extractions (Insert Data modal) |
| **Flashcards** | AI creates study cards from your documents | Documents |
| **Quizzes** | AI generates multiple-choice tests from your documents | Documents, Flashcards |
| **Stats** | Statistical analysis (descriptive + cross-tabulation) on your data files | Data & Charts (data source) |
| **Data & Charts** | Upload CSV/Excel, visualise charts | Stats |
| **Contradictions** | AI checks whether documents contradict each other on a topic | Documents |
| **Hallucination Audit** | Shows how reliable the AI's answers are (grounding score) | Ask AI |
| **Document Map** | Visual graph showing how documents and codes relate | Documents, Codes |
| **References** | Manage citations and check DOI/URL validity | Documents, Report |
| **Retention** | Set how long documents are kept before archiving or deleting | Documents |
| **Scheduled Reports** | Automatically email or generate reports on a schedule | Report |

---

## Section 1 — Overview (Project Dashboard)

### Current state
Shows stats and quick action buttons. Each button navigates away with no explanation of where it goes or why.

### Problems for non-technical users
- Numbers (documents: 12, codes: 8) have no context — good or bad? What should I do next?
- Quick action buttons have no description of what clicking them will do
- No indication of which features are "ready to use" versus "need setup first"
- No visible research progress or suggested next step

### Enhancements

**1a — Workflow Pipeline Banner**  
Below the stats row, render the 8-step workflow pipeline as a visual progress bar. Completed steps (have data) are highlighted; remaining steps are greyed out with a prompt:

```
  ✅ Upload   ✅ Ask AI   ✅ Code   ⬜ Extract   ⬜ Report   ⬜ Flashcards
              [Your next suggested step: Run Extraction →]
```

Logic: "next step" is the first step whose output count is 0 and whose prerequisite step count is > 0.

**1b — Smart Quick Actions (with context)**  
Replace plain icon buttons with richer cards showing the current count and a one-line description:

```
Before: [📄 Upload]

After:
┌──────────────────────────────────────┐
│  📄  Documents                       │
│  12 papers uploaded                  │
│  Last upload: 3 days ago             │
│  [Go to Documents →]                 │
└──────────────────────────────────────┘
```

**1c — "Things to do" panel**  
A short auto-generated checklist of suggested actions based on project state:
- ✅ Upload at least 1 document — done
- ⬜ Ask AI your first question
- ⬜ Create at least 3 codes
- ⬜ Run extraction to build a data table
- ⬜ Write your first report section

**1d — Feature readiness indicators**  
In the sidebar nav, each item shows a small status dot:
- 🟢 Ready (has data)  
- 🟡 In progress  
- ⚪ Not started  
- 🔴 Needs attention (error or empty prerequisite)

---

## Section 2 — Documents

### Current state
Upload zone, filter bar, table with file name/status/size/date/actions. Basic functionality is in place.

### Problems for non-technical users
- Status values like "indexed" / "pending" are technical — user doesn't know what indexing means
- No indication that a document is "being used" by other features
- No shortcut to start working with a document after uploading
- No connection to Codes, Extraction, Ask AI visible on this page

### Enhancements

**2a — Replace "indexed"/"pending" with friendly statuses**
| Technical | Plain language |
|---|---|
| `indexed` | ✅ Ready to use |
| `pending` | ⏳ Being processed… |
| `error` | ❌ Could not read this file |

**2b — Document activity badges**  
Each document row shows small badges summarising how much work has been done with it across the app:

```
📄 Smith et al. 2024.pdf    ✅ Ready    [Codes: 3]  [Extracted ✓]  [Asked 5×]
```

- `[Codes: 3]` → links to the Codes page filtered to this document
- `[Extracted ✓]` → links to Extraction results for this document  
- `[Asked 5×]` → links to Ask AI chat history mentioning this document

**2c — "What can I do with this document?" actions on each row**

```
📄 Smith et al.    [View]  [Ask AI about this]  [Extract Data]  [Generate Flashcards]  [⋮ more]
```

- `Ask AI about this` → opens Ask AI with `?preselect_doc={id}` (auto-focuses on this document)
- `Extract Data` → opens Extraction with `?preselect_doc={id}` (doc pre-ticked in selector)
- `Generate Flashcards` → opens Flashcards with `?preselect_doc={id}` (doc pre-selected)

**2d — Upload completion guidance**  
After uploading, instead of just returning to the table, show a small post-upload panel:

```
✅ 3 files uploaded successfully!

What would you like to do next?
  [💬 Ask AI about them]  [🏷️ Start coding themes]  [📊 Extract structured data]
```

**2e — "Extracted" / "Coded" status indicators (bidirectional with Extraction and Codes)**  
See Extraction Change 9c (already planned) and Codes Enhancement below.

---

## Section 3 — Ask AI (Search / Chat)

### Current state
A chat interface with RAG mode selector (Fast / Balanced / Deep) and several technical checkboxes (Rewrite Query, Hybrid Search, Rerank, Grounded Only). Source links appear below answers.

### Problems for non-technical users
- "RAG Mode" is a developer term — users have no idea what it means
- "Hybrid Search", "Rerank", "Rewrite Query", "Grounded Only" are incomprehensible
- Source document links appear but don't open the actual document — user can't verify
- No connection to Hallucination Audit (which tracks AI quality from this page)
- First-time users don't know what kinds of questions to ask

### Enhancements

**3a — Rename RAG Mode options with plain labels**
| Technical | Plain language |
|---|---|
| Fast | Quick answer (less reading) |
| Balanced | Standard (reads key parts) |
| Deep | Thorough (reads everything — slower) |

**3b — Replace checkbox panel with a single "Answer quality" slider**  
Replace 4 technical checkboxes with a single horizontal slider the user understands:

```
Answer quality:  [Fast ←────●──────→ Thorough]
```

Internally: Fast = fast mode, no rerank. Thorough = deep mode + rerank + rewrite. The checkboxes remain but are hidden, driven by the slider position.

**3c — Source links open the document viewer**  
Every source citation under an answer becomes a clickable link that opens the document at the exact passage the AI read. Currently source links exist but do not open to a specific location.

**3d — "Reliability indicator" per answer**  
Each AI answer shows a small grounding badge pulled from the AI's confidence score:

```
[Answer text…]
📊 Sources: Smith et al. · Jones 2023     🛡️ Reliability: High (92%)
```

Clicking `🛡️ Reliability` navigates to the **Hallucination Audit** page filtered to this session.

**3e — Starter question suggestions for new users**  
When the chat is empty, show 4 suggested question chips based on document names:

```
Try asking:
  [What are the main findings?]   [Summarise all documents]
  [What do these papers disagree on?]   [List all authors and years]
```

Clicking a suggestion fills the text input.

**3f — "Save answer to Report" button on each AI response**  
Each assistant message gets a `[+ Add to Report]` button. Clicking it opens or focuses the Report page and pastes the answer as a new section, preserving the source citations as footnotes.

---

## Section 4 — Codes

### Current state
Left sidebar with colour-coded code list and add/edit/delete. Right panel shows excerpts for the selected code. Export button.

### Problems for non-technical users
- "Codes" is qualitative research terminology — casual users don't immediately understand
- No explanation of what a code is or how to apply one to text
- No visible connection to the Matrix or Document Map
- No way to see "which documents haven't been coded yet"

### Enhancements

**4a — Rename page subtitle to plain language**  
Current subtitle: "Code your documents"  
New subtitle: "Label and categorise themes across your research"

**4b — Introductory banner (first visit)**  

```
🏷️ What are Codes?
A "code" is a label you apply to important passages in your documents.
For example, if multiple papers mention "side effects", you can mark all
those passages with a "Side Effects" code — then see them all together.

Codes you create here appear in:  [📊 Coding Matrix]  [🗺️ Document Map]  [📝 Report]
```

Banner is dismissible and persisted in `localStorage`.

**4c — Each code card shows document coverage**  
Below each code name, show: `Found in 4 of 12 documents` as a clickable link:

```
🔵 Side Effects      [Found in 4 of 12 documents →]
   18 excerpts
```

Clicking opens the **Document Map** filtered to show only documents with that code, OR a filtered view of the documents list.

**4d — "Uncoded documents" warning badge**  
If some documents have zero codes applied, show a notice at the top of the Codes page:

```
⚠️  5 documents have no codes applied yet.   [View them →]
```

Clicking links to the Documents page filtered to un-coded documents.

**4e — "Use codes in Report" shortcut**  
A button at the top of the codes list: `[+ Insert codes into Report]` — opens the Report page and triggers the "Insert Data" modal pre-filtered to codes.

**4f — Cross-links to Matrix and Document Map**  
Below the code list, a persistent footer row:

```
See your codes visualised:   [📊 Coding Matrix]   [🗺️ Document Map]
```

---

## Section 5 — Coding Matrix

### Current state
A grid showing codes (rows) vs documents (columns) with ticks where a code applies to a document.

### Problems for non-technical users
- No explanation of what the matrix is for
- "Code × Document Matrix" is abstract
- Cells are tick/empty with no count or excerpt preview
- No navigation from a cell to the actual excerpts

### Enhancements

**5a — Plain language page title and description banner**  
Title: `Code Coverage Table`  
Description banner: *"This table shows which of your codes appear in which documents. A filled cell means AI found excerpts for that code in that document. Click any cell to read the specific passages."*

**5b — Clickable cells**  
Each filled cell (code × document) becomes a clickable button that opens a side panel showing the actual excerpts for that combination, with a `[Open in Codes page →]` link.

**5c — Row and column totals**  
Add a row total (how many documents each code covers) and column total (how many codes each document has):

```
             | Smith | Jones | WHO | TOTAL
Side Effects |  ✓    |       |  ✓  |  2/3
Sample Size  |  ✓    |  ✓    |  ✓  |  3/3
TOTAL        |  2    |  1    |  2   |
```

**5d — "Document not coded" highlight**  
Columns where all cells are empty are highlighted in yellow with a tooltip: *"This document has no codes yet. Go to Documents to start coding."*

**5e — Export matrix as Excel**  
Add an "Export as Spreadsheet" button (currently only Refresh exists).

---

## Section 6 — Extraction

> Full detail already documented in `UI_UX_FIX_ENHANCEMENT_PLAN.md` (Changes 1–9).  
> Summary of key changes below for completeness.

### Planned changes (reference existing plan)
| # | Change |
|---|--------|
| 1 | Rename "Schema" → "Extraction Template" |
| 2 | Visual field builder — no JSON required |
| 3 | Preset template library (4 quick-start options) |
| 4 | Better empty and onboarding states |
| 5 | Document name in results instead of Doc ID |
| 6 | Inline contextual help at every input |
| 7 | Richer AI progress with estimated time |
| 8a | "What is Extraction?" dismissible intro banner |
| 8b | Dynamic field list callout in run panel |
| 8c | "What next?" tiles linking to Stats, Codes, Export |
| 8d | Template list shows run history and document count |
| 9a | Document selector shows Extracted/Not-yet badges |
| 9b | Result rows link to source documents |
| 9c | Documents page shows "Extracted ✓" badge |
| 9d | Template card expands to show extracted doc names |
| 9e | "Extract Data" button on each document row |

### Additional connections (not yet in the existing plan)

**6a — "Use extraction results in Report"**  
In the results table header bar, add a `[+ Insert into Report]` button — inserts the current results table as a formatted table in the Report editor.

**6b — Extraction → Stats shortcut**  
If at least one extraction result exists, show a banner: *"Your extracted data can be statistically analysed. [Go to Statistics →]"*

---

## Section 7 — Tasks

### Current state
Kanban board with To Do / In Progress / Done columns. Drag-and-drop cards with title, description, and priority.

### Problems for non-technical users
- Completely isolated — no connection to documents, codes, or any other feature
- No AI assistance for task creation
- No linked actions — a task about "code the WHO paper" has no link to the Codes page
- Priority labels (Low/Medium/High) have no visual hierarchy
- No due dates visible on cards

### Enhancements

**7a — AI "Suggest Tasks" button**  
A button `[🤖 Suggest tasks from documents]` that sends a prompt to the AI asking it to generate a task list based on the uploaded documents. The AI response is rendered as a list of "Add?" buttons:

```
AI suggests:
  [+ Add] Code all documents for "treatment outcomes"
  [+ Add] Run extraction for drug trial data
  [+ Add] Write literature review section
```

**7b — Task linking to features**  
When adding a task, offer an optional "Linked feature" dropdown:

```
Task: Code the WHO 2022 document
Linked to: [Codes page ▸]
```

When the task card is rendered, a small icon links directly to that feature. Completing all tasks linked to a feature marks that feature step as "done" on the Overview workflow pipeline.

**7c — "Create task from AI answer"**  
On the Ask AI page, each AI response gets a `[+ Create task]` button in addition to `[+ Add to Report]`. The AI answer is used as the task description.

**7d — Due dates visible on kanban cards**  
Add an optional due-date field to tasks (date picker). Cards past their due date show a red border.

**7e — Task progress on Overview**  
The Overview stats row shows: `Tasks: 3 done / 7 total` rather than just a count.

---

## Section 8 — Report

### Current state
A rich text editor (Quill.js) with a toolbar, an "Insert Data" modal, and a Share & Export button.

### Problems for non-technical users
- The "Insert Data" modal exists but users don't discover it without reading the header
- No indication of which features feed data into the report
- No visual cues about what AI can do in the editor (e.g., "Write this section for me")
- "Share & Export" is in a plain button — users don't know what formats are available

### Enhancements

**8a — "Build with your data" sidebar panel**  
Add a collapsible right panel (alongside the editor) that shows project data ready to insert:

```
📥 Insert into Report
├── 🏷️ Codes (8 codes, 42 excerpts)
│     [Insert as theme summary]
├── 📊 Extraction results (3 templates)
│     [Insert as data table]
├── 📚 References (14 citations)
│     [Insert bibliography]
└── 💬 AI answers (12 saved)
      [Insert answer]
```

Each item is a one-click insert into the editor at the current cursor position.

**8b — AI "Write this section" button**  
In the editor toolbar, add a `🤖 Write with AI` button. It opens a small panel:

```
What should this section be about?
[Using the codes and documents in this project, write a literature review...]

[Generate →]
```

The AI uses all project codes, extraction results, and document summaries as context.

**8c — Export format tooltip**  
The "Share & Export" button tooltip (or dropdown) clearly explains each format:
- **PDF** — for sharing with supervisors or submission
- **Word (.docx)** — for editing in Microsoft Word
- **HTML** — for publishing online
- **Markdown** — for developers or Obsidian/Notion

---

## Section 9 — Flashcards

### Current state
Left panel with document selector and card count. Right panel displays generated flashcard deck.

### Problems for non-technical users
- "From Documents" label with raw checkboxes — same UX issue as Extraction
- "Number of cards" dropdown has no guidance on what's a good number
- Generated flashcards are isolated — no link back to the source passage
- No quiz mode accessible from this page
- No indication that Quizzes is a related feature one step away

### Enhancements

**9a — Replace "From Documents" with named, descriptive selector**  
Label: `Which documents do you want to study?`  
Show document names with a character count or page count hint: `Smith et al. (22 pages)`

**9b — Guidance text on card count**  

```
How many flashcards?  [5 ▼]
(5–10 is ideal for first-time use. Higher counts work better for long documents.)
```

**9c — Each flashcard links to source document**  
Below each flashcard's answer, add a small `[📄 Read in Smith et al. →]` link that opens the document viewer at the passage the card was generated from (requires the backend to return a `doc_id` and `chunk_id` with each card).

**9d — "Turn into Quiz" shortcut**  
At the bottom of the flashcard deck, a button:  
`[🎯 Turn these flashcards into a Quiz →]`  
This opens the Quizzes page with the same documents pre-selected.

**9e — Connection banner on Quizzes page**  
On the Quizzes page, show: *"Already have flashcards? [Open your flashcard deck →] to study before taking a quiz."*

---

## Section 10 — Quizzes

### Current state
Left panel with document selector, quiz name, question count. Right panel shows quiz list.

### Problems for non-technical users
- Same issues as Flashcards (document selector, no source links)
- Quiz results show correct/wrong but no link to read more in the source document
- No difficulty modes ("Easy hints", "No hints")
- No score tracking over time

### Enhancements

**10a — Source links on wrong answers**  
When a user answers a question incorrectly, the correct answer panel shows: `[📄 Read more in Jones 2023 →]` linking to the relevant passage.

**10b — Difficulty toggle**  
```
Difficulty:  [Easy — show hints]  [Standard]  [Hard — no hints]
```

Easy mode: shows which document the answer comes from. Hard mode: no document hints.

**10c — Score history badge**  
In the quiz list, each quiz card shows: `Last score: 4/5 (80%)` and a trend arrow (↑ improving / → same / ↓ declining) if attempted more than once.

**10d — "Study first" prompt if no flashcards exist**  
If the user tries to take a quiz on documents that have no flashcards, show:  
*"Generate flashcards first to warm up. [Create flashcards for these documents →]"*

---

## Section 11 — Statistics

### Current state
Summary stat cards (Documents, Flashcards, Quizzes, Codes), two charts (Documents by Type, Activity Over Time), and a Data Source Statistics panel with Describe and Cross-tabulation tools.

### Problems for non-technical users
- "Descriptive statistics" and "Cross-tabulation" are statistical jargon
- The data source selector is disconnected from the Data & Charts page — user doesn't know they need to upload data there first
- No plain-language interpretation of statistical results

### Enhancements

**11a — Plain language stat labels**
| Technical | Plain language |
|---|---|
| Descriptive statistics | Summary of your data |
| Cross-tabulation | Compare two categories |
| Describe | Analyse |

**11b — "No data source" empty state with direct link**  
If no CSV/Excel has been uploaded, instead of a broken dropdown, show:

```
📊 To run statistical analysis, first upload a data file.
[Go to Data & Charts to upload your spreadsheet →]
```

**11c — Plain-language result interpretation**  
After running Describe, add an AI-generated one-sentence plain summary above the raw output:

```
[AI Summary] Your data has 150 rows. The average sample size is 42 with a range of 10 to 210.

[Raw output below ▼]
count    150
mean     42.3
...
```

**11d — "Use in Report" button on results**  
Each analysis result (Describe output, Cross-tab table) has a `[+ Insert into Report]` button.

---

## Section 12 — Data & Charts

### Current state
Upload zone for CSV/Excel, a saved charts list, a chart builder panel.

### Problems for non-technical users
- "Saved Charts" heading with no indication that charts can be inserted into the Report
- No link to the Statistics page even though they share the same data sources
- Chart type names (Bar, Line, Pie, Scatter) with no example thumbnails

### Enhancements

**12a — Connection to Stats**  
A persistent notice at the top:  
*"Data files you upload here are also available in the [Statistics page →] for numerical analysis."*

**12b — "Insert chart into Report"**  
Each saved chart has an `[+ Add to Report]` button.

**12c — Chart type picker with thumbnails**  
Replace the dropdown of chart types with small thumbnail preview cards showing what each chart looks like.

---

## Section 13 — Contradictions

### Current state
Left panel with claim/statement textarea and "Search In" document selector. Right panel shows results. (Translation fixes planned separately.)

### Problems for non-technical users
- Users don't understand they need to type a **claim to check**, not a search query
- "Search In" doesn't explain the purpose — user doesn't know they can limit which documents are checked
- No connection to Hallucination Audit (which tracks similar quality concerns)
- No link to the Documents page to see which documents were checked

### Enhancements

**13a — Plain language explanation of the claim input**  
Label: `Statement to verify`  
Helper text: *"Type something you believe to be true — or something from your documents — and AI will check whether any other document contradicts it."*  
Placeholder: `e.g. "All studies found a positive correlation between X and Y"`

**13b — "Search In" → "Which documents to check?"**  
Replace label with: `Which documents should AI compare?` and add a `(Check all)` shortcut.

**13c — "Try checking these statements" suggestions**  
If documents are AI-indexed, suggest 3 auto-generated claims pulled from the documents to check:

```
Not sure what to check? Try these based on your documents:
  ["The study found no significant adverse effects"]
  ["Sample sizes above 100 are required for statistical power"]
```

**13d — Connection banner to Hallucination Audit**  
After results, show: *"Want to check how reliable your AI answers are overall? [Go to AI Reliability Audit →]"*

---

## Section 14 — Hallucination Audit

### Current state
Four stat cards (Total, Flagged, Avg Score, Pass Rate), a table of recent audit entries with step name, score badge, flag icon, answer preview, and date.

### Problems for non-technical users
- "Hallucination Audit" is a technical AI term — users don't know what it means
- "Grounding score" and "flagged" need explanation
- Table shows "step name" (technical pipeline names) rather than the question the user asked
- No link back to the original Ask AI question that triggered each entry

### Enhancements

**14a — Rename page title and subtitle**  
Title: `AI Reliability Report`  
Subtitle: `See how accurate and trustworthy the AI's answers have been`

**14b — Explain the score in the stat cards**  

```
🛡️ Reliability Score: 87%
(87 out of 100 AI answers were based directly on your documents)
```

**14c — Replace "step name" with the actual question asked**  
If the audit entry was triggered by an Ask AI query, store and display the original question:

```
Before: step_rag_retrieve
After:  "What were the side effects reported in the studies?"
```

**14d — "Read this answer" link on each row**  
Each row in the table gets a `[💬 View in Ask AI →]` link that opens the Ask AI conversation where that answer was generated.

**14e — "Flagged answers" explanation**  
Next to the Flagged stat: a tooltip/popover: *"Flagged answers are ones where the AI could not find strong evidence in your documents. You should verify these manually."*

---

## Section 15 — Document Map

### Current state
A canvas (`#mapCanvas`) that renders a graph (nodes = documents and codes, edges = relationships). A small label below.

### Problems for non-technical users
- No explanation of what the graph shows or how to read it
- No interaction — clicking a node does nothing
- No legend explaining the colours of nodes
- Completely isolated — no way to navigate from a node to the relevant page

### Enhancements

**15a — Explanation banner**  
*"This map shows how your documents (blue) and themes/codes (purple) are connected. A line means that code appears in that document. Clusters show groups of documents that share similar themes."*

**15b — Clickable nodes**  
- Clicking a document node → opens the document viewer for that document
- Clicking a code node → opens the Codes page filtered to that code
- Hovering a node → shows a tooltip with name + count

**15c — Legend**  
A small fixed legend in the corner: `● Documents (blue)  ● Codes (purple)  — Shared theme`

**15d — "No data" empty state with actionable link**  
If no codes exist: *"Your map will appear once you start applying codes to documents. [Go to Codes →]"*

---

## Section 16 — References

### Current state
A page for managing citations — DOI/URL validation, import from BibTeX.

### Problems for non-technical users
- "References" is clear but its connection to the Report is invisible
- Users don't know that validated references can be inserted into the Report as a bibliography
- DOI validation result ("Valid" / "Invalid") doesn't explain what a DOI is

### Enhancements

**16a — DOI explanation tooltip**  
Next to "DOI" field: an info icon → *"A DOI (Digital Object Identifier) is the unique code for a published paper, e.g. 10.1016/j...."*

**16b — "Add to Report bibliography" button**  
Each validated reference shows: `[+ Add to Report]` — inserts the citation in the Report's reference list.

**16c — "References you might be missing" suggestions**  
After running extraction, cross-reference the Author/Year fields in extraction results against the References list. If an author in extraction results is not in References, show a notice:

```
📚 We noticed "Smith et al. 2024" appears in your extraction results but is not in your References.
   [Add reference for Smith et al. →]
```

---

## Section 17 — Retention

### Current state
Left panel with policy settings (period in days, action dropdown, save). Right panel with affected documents list.

### Problems for non-technical users
- Completely isolated — no connection to Documents shown
- "Archive automatically" and "Delete automatically" are understated for something that destroys data
- Users need a clear warning before enabling deletion
- No indication of how many documents would be affected until after saving

### Enhancements

**17a — Live "documents affected" preview before saving**  
As the user types a retention period, immediately update the right panel with a live count:

```
If you set 365 days:  3 documents would be flagged for review
                       0 documents would be archived
                       0 documents would be deleted

⚠️ This will permanently remove documents older than 365 days.
```

**17b — Explicit delete warning dialog**  
If "Delete automatically" is selected, the Save button shows a red confirmation dialog: *"⚠️ This will permanently delete matching documents. This cannot be undone. Are you sure?"*

**17c — Affected documents are clickable**  
The affected documents list shows document names as links to the document viewer, so users can review them before saving the policy.

---

## Section 18 — Scheduled Reports

### Current state
A list of scheduled report configurations with timing and format.

### Problems for non-technical users
- Unclear what a "scheduled report" will contain — is it the full report, a summary, stats?
- No connection to the Report page to preview what will be sent
- Frequency options are technical (cron-style); need plain labels (Daily / Weekly / Monthly)

### Enhancements

**18a — "Preview this report" button**  
Each scheduled report configuration shows a `[Preview →]` link that opens the Report page to show what the current report looks like.

**18b — Plain frequency options**  
Replace any cron syntax with: `Daily / Weekly / Monthly / Every time a new document is uploaded`

**18c — Last sent / next send indicator**  
Each schedule shows: `Last sent: Feb 20, 2026 · Next: Mar 1, 2026`

---

## Inter-Feature Connection Map

The table below is the **master connection reference** — every directed link that should exist between features. Items marked ⚠️ do not currently exist and need to be built.

| From | To | Connection | Status |
|------|----|-----------|--------|
| Documents | Ask AI | "Ask AI about this" button per document | ⚠️ New |
| Documents | Extraction | "Extract Data" button per document | ⚠️ New |
| Documents | Flashcards | "Generate Flashcards" button per document | ⚠️ New |
| Documents | Codes | "Coded: 3 themes" badge per document | ⚠️ New |
| Ask AI | Documents | Source citation links open document viewer | ⚠️ Needs fixing |
| Ask AI | Report | "Add to Report" button on each answer | ⚠️ New |
| Ask AI | Tasks | "Create task from this answer" button | ⚠️ New |
| Ask AI | Hallucination Audit | Reliability badge on each answer | ⚠️ New |
| Codes | Matrix | "See codes in matrix" link in footer | ⚠️ New |
| Codes | Document Map | "See codes in map" link in footer | ⚠️ New |
| Codes | Report | "Insert codes into Report" button | ⚠️ New |
| Codes | Documents | "Uncoded documents" warning badge | ⚠️ New |
| Matrix | Codes | Clicking a cell opens Codes page at that code | ⚠️ New |
| Matrix | Documents | Clicking a column header opens that document | ⚠️ New |
| Extraction | Documents | "Extracted ✓" badge on each document row | ⚠️ New |
| Extraction | Report | "Insert results table into Report" button | ⚠️ New |
| Extraction | Stats | "Analyse in Statistics" tile after extraction | ⚠️ New |
| Extraction | Documents | Result rows link to source document | ⚠️ New |
| Flashcards | Documents | Each card links to source passage | ⚠️ New |
| Flashcards | Quizzes | "Turn into Quiz" button at bottom of deck | ⚠️ New |
| Quizzes | Documents | Wrong answers link to source passage | ⚠️ New |
| Quizzes | Flashcards | "Study with flashcards first" prompt | ⚠️ New |
| Stats | Data & Charts | "Upload data in Data & Charts first" prompt | ⚠️ New |
| Stats | Report | "Insert analysis into Report" button | ⚠️ New |
| Data & Charts | Stats | "Run statistics on this data" link | ⚠️ New |
| Data & Charts | Report | "Insert chart into Report" button | ⚠️ New |
| Report | Codes | "Build with your data" sidebar panel | ⚠️ New |
| Report | Extraction | Insert extraction results as table | ⚠️ Partially exists (Insert Data modal) |
| Report | References | Insert bibliography from References | ⚠️ New |
| Report | Scheduled Reports | "Auto-send this report" link | ⚠️ New |
| Contradictions | Documents | Results show which documents contradict | Exists |
| Contradictions | Hallucination Audit | "Check AI reliability overall" link | ⚠️ New |
| Hallucination Audit | Ask AI | Each audit row links back to original question | ⚠️ New |
| Document Map | Documents | Clicking document node opens document | ⚠️ New |
| Document Map | Codes | Clicking code node opens Codes page | ⚠️ New |
| References | Report | "Add to Report bibliography" per reference | ⚠️ New |
| References | Extraction | "Missing reference" alert from extraction results | ⚠️ New |
| Overview | All features | Workflow pipeline with progress indicators | ⚠️ New |
| Tasks | Features | Task cards link to relevant feature page | ⚠️ New |

---

## Implementation Priority

### Phase 1 — Highest impact, least effort (Quick wins)
1. Documents page: activity badges + "Ask AI / Extract / Flashcards" action buttons per row  
2. Ask AI: rename RAG modes + source links that open document viewer  
3. Codes: cross-links to Matrix and Document Map in footer  
4. Flashcards → Quizzes: "Turn into Quiz" button  
5. Stats: "no data source" empty state with link to Data & Charts  
6. All extraction changes (already planned in `UI_UX_FIX_ENHANCEMENT_PLAN.md`)  

### Phase 2 — Medium effort, high user impact
1. Overview: workflow pipeline banner with progress  
2. Report: "Build with your data" right panel  
3. Ask AI: "Add to Report" and "Create task" buttons on each answer  
4. Document Map: clickable nodes  
5. Hallucination Audit: link rows back to Ask AI questions  
6. Codes: uncoded documents badge  

### Phase 3 — Requires backend changes
1. Flashcards and Quizzes: source passage links (requires `chunk_id` in API response)  
2. References: "missing reference" detection from extraction results  
3. Tasks: AI task suggestions from documents  
4. Stats: AI plain-language result interpretation  
5. Documents: "Coded / Extracted / Asked" badge counts (requires cross-table queries)  

---

## Verification Checklist (Full App)

- [ ] Overview shows workflow pipeline with correct step completion state
- [ ] Every document row has "Ask AI / Extract / Flashcards" action buttons
- [ ] Every document row shows Codes/Extracted/Asked activity badges
- [ ] Ask AI source citations open the document at the correct passage
- [ ] Ask AI answers have "Add to Report" and "Create Task" buttons
- [ ] Codes page has cross-links to Matrix and Document Map
- [ ] Matrix cells are clickable (opens excerpts side panel)
- [ ] Document Map nodes are clickable (opens relevant page)
- [ ] Flashcards link to source documents + have "Turn into Quiz" shortcut
- [ ] Quizzes: wrong answers link to source document passage
- [ ] Stats: empty state links to Data & Charts upload
- [ ] Stats results have "Insert into Report" button
- [ ] Data & Charts: saved charts have "Add to Report" button
- [ ] Report: "Build with your data" sidebar shows codes/extraction/references
- [ ] Retention: live affected-document preview before saving
- [ ] Hallucination Audit rows link back to Ask AI conversation
- [ ] Contradictions page has link to Hallucination Audit
- [ ] References page has "Add to Report" per citation
- [ ] Scheduled Reports shows last/next send dates
- [ ] All new strings use `t()` and are in all 4 locale files
- [ ] All intro banners are dismissible and persist in `localStorage`
- [ ] All new cross-links use correct `url_for()` calls (no hardcoded paths)
