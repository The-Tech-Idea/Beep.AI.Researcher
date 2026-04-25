# Phase 5 — Researcher Social Network

> **Feature flag**: `social_network_enabled`
> **Inspired by**: ResearchGate, Academia.edu
> **Depends on**: Phase 4 (published manuscript sections raise profile metrics)
> **Unlocks**: Standalone enrichment; feeds Phase 3 co-author edges
>
> **Existing foundation to BUILD ON**:
> - `routes/collaboration.py` — project-scoped membership: `ProjectMember` (viewer | contributor | admin), `ProjectComment`.
>   Phase 5 adds the **cross-project identity layer** on top (researcher profiles, follow, impact metrics).
>   `collaboration.py` is NOT replaced; it remains the per-project team management surface.
> - The `ProjectMember` model's `user_id` becomes the anchor for the new `ResearcherProfile`.
> - `User` model already has `email`, `username`, `role_id`; `ResearcherProfile` extends it with
>   display_name, bio, ORCID, visibility_level, etc. via a separate 1-to-1 model (not adding columns to `User`).
> - `routes/tasks.py` + `ResearchTask` + `TaskNotification` already exist and are feature-complete.
>   Phase 5 does NOT recreate task management. The **activity feed** reads from task events as one
>   of several social signal sources, but task routes/models are untouched.
> - `routes/training.py` + `Quiz`/`QuizAttempt`/`Flashcard` models already provide study features.
>   Phase 5 may surface quiz scores as profile metrics; it does NOT add new quiz logic.
> - `static/js/profile.js` + `templates/profile.html` partially scaffold profile UI.
>   Phase 5 extends this rather than starting from scratch — check what already renders.

---

## 1. Goal

Build an opt-in social layer that lets researchers share discovery, follow each
other's work, and build a measurable research identity — all within the
platform they already use for their daily research work.

Privacy-first: every social feature is opt-in. Researchers control visibility of
their profile, publications, and activity.

---

## 2. Features

### 2.1 Researcher Profile

A public-facing profile page for each user who opts in.

**User actions**
- Navigate to Settings → Public Profile to create and edit their profile.
- Set: display name, institution, research areas (multi-select from existing
  interest profiles), bio, ORCID, LinkedIn/website links.
- Control visibility: Public / Platform only / Private (default).
- View their own published profile as others would see it.
- View other researchers' profiles via `/researchers/<username>`.

**Profile content** (auto-populated from existing system data)
- Projects (shared with permission)
- Publications (from Reference model, can be flagged as "my publication")
- Research interests (from Phase 1 `ResearchInterestProfile`)
- Metrics: total papers saved, collaborations count, profile views

**Architecture**
- New model: `ResearcherProfile` (extends `User` data, not a second user record).
- New service: `ProfileService` — CRUD, visibility enforcement, metric aggregation.
- Route: `GET /researchers/<username>` — public profile page.
- Route: `GET /settings/profile` — edit profile page.
- Route: `POST /settings/profile` — save profile.

### 2.2 Follow System

Researchers follow other researchers or projects to receive activity updates.

**User actions**
- Click "Follow" on any researcher profile (if visibility allows).
- Click "Follow project" on any project shared publicly.
- View followed researchers and projects in Settings → Following.
- Unfollow at any time.

**System behaviour**
- Following a researcher queues their published activity into the follower's
  Activity Feed (see 2.4).
- Following a project queues new documents, publications, and synthesis reports
  added to that project.
- No notifications are sent to the person being followed (privacy default).

**Architecture**
- New model: `Follow` — `(follower_id, followee_user_id NULLABLE, followee_project_id NULLABLE)`.
- Unique constraint: one follow per (follower, followee) combination.
- Service: `FollowService` — follow/unfollow; list followers/following.
- Route: `POST /researchers/<username>/follow`
- Route: `DELETE /researchers/<username>/follow`
- Route: `POST /projects/<pid>/follow`
- Route: `DELETE /projects/<pid>/follow`

### 2.3 Research Impact Metrics Dashboard

A personal metrics page showing measurable research activity over time.

**User actions**
- Navigate to Profile → Impact to view their dashboard.
- See metrics:
  - **Library growth**: papers added over time (line chart, monthly).
  - **Project activity**: documents, annotations, flashcards per project (bar chart).
  - **Publications**: list of own papers with external citation count (from Semantic Scholar).
  - **Profile views**: 30-day rolling count.
  - **Collaboration count**: number of unique co-project members.
- Export metrics as PDF or CSV.

**System behaviour**
- All metrics computed from existing data: `ResearcherDocument`, `Reference`,
  `ProjectMember`, `ResearcherProfile.profile_views`.
- External citation count: one-time fetch from Semantic Scholar API per DOI,
  cached for 7 days in `CitationCountCache`.
- Metrics page rendered with the existing observability/reporting infrastructure
  (charts JS already in the project).

**Architecture**
- New service: `ImpactMetricsService` — aggregates data, calls Semantic Scholar.
- New model: `CitationCountCache` (doi, citation_count, fetched_at).
- Route: `GET /profile/impact` — impact dashboard page.
- Route: `GET /profile/impact/data` — JSON metrics data.

### 2.4 Activity Feed

A chronological stream of research activity from followed researchers and projects.

**User actions**
- Navigate to "Network" in the main nav.
- See activity cards from followed researchers/projects:
  - "Researcher X added 5 papers to Project Y"
  - "Researcher X published a synthesis on topic Z"
  - "Project Y reached 100 documents"
- Click activity cards to navigate to the related resource.
- Filter feed: My Activity / Following / Suggestions.

**System behaviour**
- Activity events generated by the existing event bus when:
  - A document is added to a shared project.
  - A synthesis report is completed (Phase 2).
  - A manuscript is exported/shared.
  - A researcher reaches a milestone (100 papers, first collaboration).
- Events stored in `ActivityEvent` model.
- Feed query: `ActivityEvent WHERE actor IN (followed researchers) UNION own events ORDER BY created_at DESC LIMIT 50`.

**Architecture**
- New model: `ActivityEvent` — FK to actor `User`, event_type, payload JSON, visibility.
- New service: `ActivityFeedService` — event creation hooks + feed query.
- Hook registered on the existing event bus for document add, synthesis complete, etc.
- Route: `GET /network/` — activity feed page.
- Route: `GET /network/data` — paginated JSON feed.

### 2.5 Research Network Visualisation

A mini graph (reusing Phase 3 infrastructure) showing the researcher's
collaboration network: who they have worked with, on what project, over what time.

**User actions**
- On the Profile page, see "My network" panel with a small force-directed graph.
- Nodes: researchers they have collaborated with on at least one project.
- Edges: projects (edge count = number of shared projects).
- Click a node to view that researcher's profile.

**Architecture**
- `KnowledgeGraphService.build_collaboration_graph(user_id)` — reuses Phase 3 node/edge
  contracts but with co-author type edges.
- Route: `GET /profile/network-data` — returns graph JSON.
- Frontend: reuses Phase 3 graph rendering JS (shared component).

### 2.6 Collaboration Invitations

Improve the existing project-member invite flow with a social discovery layer.

**User actions**
- When inviting a project member, search by name or research interest (not just email).
- See profile cards for matched researchers (photo, interests, institution).
- Send invitation with a personalised note.

**Architecture**
- `GET /projects/<pid>/members/search?q=` — existing route extended with
  profile-aware search when `social_network_enabled`.
- `ProfileService.search_researchers(query)` — searches by display name, institution,
  research interest.

---

## 3. New Models

### `ResearcherProfile`
```
id                  INTEGER PK
user_id             INTEGER FK(user.id) UNIQUE NOT NULL
username            TEXT UNIQUE NOT NULL
display_name        TEXT NOT NULL
institution         TEXT
bio                 TEXT
orcid               TEXT
website_url         TEXT
visibility          TEXT NOT NULL DEFAULT 'private'   -- 'public' | 'platform' | 'private'
profile_views       INTEGER NOT NULL DEFAULT 0
created_at          DATETIME NOT NULL
updated_at          DATETIME NOT NULL
```
Index: `(username)`, `(visibility)`
Migration: `add_researcher_profile`

### `Follow`
```
id                      INTEGER PK
follower_id             INTEGER FK(user.id) NOT NULL
followee_user_id        INTEGER FK(user.id) NULLABLE
followee_project_id     INTEGER FK(research_project.id) NULLABLE
created_at              DATETIME NOT NULL
UNIQUE (follower_id, followee_user_id)
UNIQUE (follower_id, followee_project_id)
CHECK (followee_user_id IS NOT NULL OR followee_project_id IS NOT NULL)
```
Migration: `add_follow`

### `ActivityEvent`
```
id              INTEGER PK
actor_id        INTEGER FK(user.id) NOT NULL
event_type      TEXT NOT NULL
payload         JSON NOT NULL DEFAULT '{}'
visibility      TEXT NOT NULL DEFAULT 'platform'   -- 'public' | 'platform' | 'private'
created_at      DATETIME NOT NULL
```
Index: `(actor_id, created_at)`, `(event_type, created_at)`
Migration: `add_activity_event`

### `CitationCountCache`
```
id              INTEGER PK
doi             TEXT NOT NULL UNIQUE
citation_count  INTEGER NOT NULL DEFAULT 0
fetched_at      DATETIME NOT NULL
```
Migration: `add_citation_count_cache`

---

## 4. New Services

| Service | Responsibilities |
|---|---|
| `ProfileService` | CRUD; visibility enforcement; metric aggregation |
| `FollowService` | Follow/unfollow; list followers; permission checks |
| `ImpactMetricsService` | Aggregate library/collab metrics; external citation counts |
| `ActivityFeedService` | Event creation; feed query; pagination |

---

## 5. New Routes

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/researchers/<username>` | Public researcher profile |
| `GET` | `/settings/profile` | Edit profile page |
| `POST` | `/settings/profile` | Save profile |
| `POST` | `/researchers/<username>/follow` | Follow researcher |
| `DELETE` | `/researchers/<username>/follow` | Unfollow researcher |
| `POST` | `/projects/<pid>/follow` | Follow project |
| `DELETE` | `/projects/<pid>/follow` | Unfollow project |
| `GET` | `/network/` | Activity feed page |
| `GET` | `/network/data` | Paginated activity JSON |
| `GET` | `/profile/impact` | Impact dashboard page |
| `GET` | `/profile/impact/data` | Metrics JSON |
| `GET` | `/profile/network-data` | Collaboration graph JSON |

---

## 6. UI Design

> See **MODEL.md §10** for global nav, hub architecture, shared components, and the full file inventory.
> This section covers the interaction design unique to Phase 5.

### 6.1 File Pairs

| Template | JS | CSS |
|---|---|---|
| `templates/social/researcher_profile.html` | `static/js/social/researcher_profile.js` | `static/css/social/researcher_profile.css` |
| `templates/social/network_feed.html` | `static/js/social/network_feed.js` | *(shared theme)* |
| `templates/social/impact_dashboard.html` | `static/js/social/impact_dashboard.js` | `static/css/social/impact_dashboard.css` |
| `templates/settings/profile.html` | `static/js/settings/profile.js` | *(shared theme)* |

### 6.2 ProfileCard Component (shared)

The `ProfileCard` is a shared component defined in `static/js/components/paper_card.js` (extended variant). Reused:
- `researcher_profile.html` — large variant with metrics.
- `network_feed.html` activity items — small chip variant (avatar + name + institution).
- Knowledge Map co-author ghost nodes side panel — compact variant.
- Search results — compact variant.

**Large profile card anatomy**:
```
+----------------------------------------------------+
| [Avatar]  Display Name                             |
|           Institution · ORCID (linked)             |
|           Research areas: [tag] [tag] [tag]        |
|  Publications: 42   H-index: 12   Citations: 890   |
|  Followers: 34    Following: 18                    |
|             [Follow / Following v]  [Message]      |
+----------------------------------------------------+
```

**Follow button states**:
- Not following: filled primary button "Follow".
- Following: outlined button "Following" with hover text "Unfollow".
- Own profile: button hidden.
- Unfollow requires `ConfirmDialog`: "Unfollow [Name]? They will no longer see your activity."

### 6.3 Researcher Profile Page (`/social/researchers/<user_id>`)

Below the profile card: two-tab layout — **Publications** | **Activity**.

**Publications tab**: table (title, year, citations, venue). Each row has "View in Knowledge Map" link (cross-phase action to Phase 3, MODEL.md §10.4).

**Activity tab**: same `ActivityFeedItem` components as `network_feed.html` filtered to this researcher.

### 6.4 Activity Feed (`/social/feed/`)

**ActivityFeedItem types**:

| Event type | Display |
|---|---|
| New paper published | ProfileChip + "published a new paper" + compact `PaperCard` |
| New synthesis | ProfileChip + "ran a synthesis on [topic]" + link to report |
| New follower | ProfileChip + "started following [Name]" |
| Published section | ProfileChip + "published a writing section" + excerpt |
| New alert match | "[n] papers matching your interests" — consolidates Phase 1 alerts |

Feed uses infinite scroll (IntersectionObserver). Empty state: "Follow researchers to see their activity here. [Find Researchers]"

### 6.5 Impact Dashboard (`/social/impact/`)

Three metric cards (top row): Publications · H-index · Total Citations.

Below: two panels side by side:
- **Citations over time** — sparkline bar chart (Chart.js from CDN, 60 px height micro-chart).
- **Research area breakdown** — donut chart of publication count by topic tag.

Visibility toggle group below metric cards:
- Three-option toggle: **Public** | **Platform only** | **Private**.
- "Private" hides all metrics from other users. Own dashboard always shows full data.

CTA at bottom: **"Open my personalised feed"** — navigates to Phase 1 feed with interest profile scoped to user's research areas (MODEL.md §10.4).

### 6.6 Privacy-First Empty States

When viewing another user's profile with metrics set to Private:
> "[Name] keeps their impact metrics private."

When following list is empty:
> "You are not following anyone yet. [Find Researchers] to discover collaborators."

---

## 7. Tests

| File | Scope |
|---|---|
| `tests/test_profile_service.py` | CRUD; visibility; metric aggregation |
| `tests/test_follow_service.py` | Follow/unfollow; constraints; privacy |
| `tests/test_impact_metrics_service.py` | Aggregation; mocked Semantic Scholar |
| `tests/test_activity_feed_service.py` | Event creation; feed query; pagination |
| `tests/test_social_routes.py` | Route contracts; follow visibility enforcement |

---

## 8. Acceptance Criteria

- [ ] A Private profile is invisible to all other users; route returns 404.
- [ ] A Platform-only profile is visible to logged-in users but returns 404 to unauthenticated.
- [ ] Following a researcher adds their events to the follower's activity feed.
- [ ] Activity feed is paginated and does not load more than 50 events per page.
- [ ] Impact dashboard shows correct paper count matching `ResearcherDocument` records.
- [ ] External citation count is cached and does not re-fetch within 7 days.
- [ ] Collaboration network graph loads within 2 s for researchers with < 50 collaborators.
- [ ] Profile search by research interest returns ranked results.
- [ ] All social routes return 404 when `social_network_enabled=False`.
- [ ] No social data is created for a user until they explicitly opt in via Settings → Profile.
