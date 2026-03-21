---
name: bdc-frontend
description: >
  Complete frontend development standards, templates, and conventions for the BDC
  CoreApplication Next.js frontend. Use this skill for every task that touches files
  inside frontend/src/ — whether creating components, hooks, service calls, page routes,
  API route handlers, Tailwind styling, dark mode, modals, forms, or any new feature area.
  Also consult this skill when wiring up environment variables, writing proxy-aware fetches,
  or reviewing existing code for consistency with project conventions.
---

# BDC Frontend — Complete Developer Skill

> **Runtime:** Node.js 20 (Alpine) · **Framework:** Next.js 14 App Router · **Language:** TypeScript (`strict: true`, `noImplicitAny: false`)
> **Styling:** Tailwind CSS + shadcn/ui
> **Auth:** NextAuth.js (credentials provider, JWT sessions)
> **Backends:** Auth/Management Service `:8080` · LMS Service `:8081`
> **Production URL:** `https://bdc.hpcc.vn`

---

## 1. Full Directory Map

```
frontend/
├── .env                          # Local secrets — NEVER commit
├── next.config.ts                # Proxy rewrites, image domains, webpack splits
├── tsconfig.json                 # paths: "@/*" → "./src/*"
├── Dockerfile                    # 3-stage: deps → builder → runner (standalone output)
│
└── src/
    ├── app/                      # Next.js App Router — ONLY layouts and page shells
    │   ├── layout.tsx            # Root layout: ThemeProvider, fonts, MainProvider
    │   ├── globals.css
    │   ├── error.tsx
    │   │
    │   ├── (auth)/               # Route group — auth layout (no sidebar)
    │   │   ├── layout.tsx
    │   │   ├── login/page.tsx
    │   │   └── confirm-password-change/page.tsx
    │   │
    │   ├── (landing)/            # Public pages — landing layout
    │   │   ├── layout.tsx
    │   │   ├── page.tsx          # Home / landing
    │   │   ├── hackathon2025/page.tsx
    │   │   └── forms/survey/[survey_name]/page.tsx
    │   │
    │   ├── (main)/               # Authenticated app — MainLayout (Sidebar + Footer)
    │   │   ├── layout.tsx        # Wraps: Sidebar (desktop) + MobileNav + Footer
    │   │   ├── dashboard/page.tsx
    │   │   ├── events/page.tsx
    │   │   ├── leaderboard/page.tsx
    │   │   ├── myaccount/page.tsx
    │   │   ├── tasks/page.tsx
    │   │   └── users/page.tsx
    │   │
    │   ├── (learning)/lms/       # LMS area — own layout hierarchy
    │   │   ├── layout.tsx        # LMS shell
    │   │   ├── page.tsx          # LMS home
    │   │   ├── admin/            # Admin dashboard + youtube-manage
    │   │   ├── student/          # Student courses, quiz take/result/history/stats
    │   │   ├── teacher/          # Teacher courses create/manage, quiz grading/manage
    │   │   └── forums/           # Forum by content + post detail
    │   │
    │   └── api/                  # Next.js Route Handlers (server-side only)
    │       ├── auth/[...nextauth]/route.ts   # NextAuth handler
    │       ├── auth/token/route.ts           # Custom token endpoint
    │       ├── health/route.tsx              # Docker healthcheck target
    │       ├── submit-form/route.ts          # Google Script form proxy
    │       ├── upload/route.ts               # File upload handler
    │       └── youtube/                      # YouTube OAuth flow (6 routes)
    │
    ├── components/
    │   ├── ui/                   # shadcn/ui primitives — do not modify directly
    │   │   └── button, input, dialog, card, badge, avatar, select,
    │   │       label, textarea, tooltip, dropdown-menu, sheet, CountDown
    │   │
    │   ├── layout/               # App chrome
    │   │   └── Sidebar, MobileNav, Navbar, Footer, Background, Feature, Logo
    │   │
    │   ├── common/               # Cross-feature shared components
    │   │   └── SafeImage.tsx
    │   │
    │   ├── dashboard/            # (main)/dashboard feature
    │   │   ├── DashboardHeader.tsx
    │   │   ├── StatsCards.tsx
    │   │   ├── SectionHeader.tsx
    │   │   ├── ShowMoreButton.tsx
    │   │   ├── LoadingState.tsx
    │   │   ├── announcement/     AnnouncementCard, AnnouncementList
    │   │   ├── event/            EventCard, EventList
    │   │   ├── calendar/         Calendar, CalendarDayCell, CalendarHeader,
    │   │   │                     CalendarLegend, MultiDayTaskBar, TaskChip,
    │   │   │                     TaskDetailPanel
    │   │   └── modals/           AnnouncementModal, EventModal, modalStyles.ts
    │   │
    │   ├── events/               EventDetails, EventHero, EventRegistration, EventTimeline
    │   ├── Board/                Kanban — BoardColumn, TaskCard, TaskModal, TaskScoreModal
    │   ├── form/                 Survey — QuestionComponents, SurveyForm, SurveyParts
    │   ├── home/                 Landing sections — About, Activities, Hero, Members, Projects
    │   ├── icons/                Icons, MenuIcon, XIcon
    │   ├── login/                LoginForm, ConfirmPasswordForm, InvalidTokenCard, Mascot
    │   ├── user/                 Avatar, DetailModal, PasswordChangeForm, UserApp, UserRow
    │   │   └── manage/           AccountStats, AvatarUpload, MessageAlert, PasswordTab, ProfileTab
    │   └── lms/
    │       ├── shared/           Reusable LMS primitives: Alert, Badge, Button, Card,
    │       │                     CourseCard, EmptyState, Spinner, TabBar, StatCard, etc.
    │       ├── admin/            ActionCard, PendingEnrollmentItem, ProgressBar, StatCard
    │       ├── forum/            ForumView, ForumPostList, ForumPostCard, ForumPostDetail,
    │       │                     ForumCommentSection, ForumCommentItem, ForumCreatePost,
    │       │                     ForumSearchBar
    │       ├── student/          AIDiagnosisModal, ContentViewer, FileUploadQuestion,
    │       │                     FillBlankDropdownStudent, FillBlankTextStudent,
    │       │                     QuizHistoryModal, QuizReviewModal, SpacedRepetitionWidget
    │       │   └── stats/        CourseProgressSection, QuizScoreSection, StatsHeroCards
    │       └── teacher/          AINodeManager, AIQuizGenPanel, BulkUploadModal,
    │                             ContentModal, ContentPickerModal, EditContentModal,
    │                             EditCourseModal, FileUpload, FillBlankDropdownEditor,
    │                             FillBlankTextEditor, OverviewTab, QuestionImageUploader,
    │                             QuizSelectorModal, QuizSettingsForm, SectionModal,
    │                             StudentTab, YoutubeVideoUpload
    │                 └── students/  StudentDetailPanel, StudentProgressTable, StudentSummaryBar
    │
    ├── hooks/
    │   ├── useAuth.tsx           Session + admin guard (wraps NextAuth useSession)
    │   ├── useCurrentUser.tsx    Current user profile from backend
    │   ├── useAnnouncements.tsx  Announcement list + CRUD + modal state
    │   ├── useEvents.tsx         Event list + CRUD + modal state
    │   ├── useTasks.tsx          Kanban task state
    │   ├── useTaskScores.tsx     Task scoring
    │   ├── useCalendarTasks.tsx  Calendar task view
    │   ├── usePagination.tsx     Generic paginated slice of any array
    │   ├── useTutorialManager.ts
    │   └── animation/useScrollAnimation.ts
    │
    ├── services/                 ALL fetch() calls live here — never in components/hooks
    │   ├── api.ts                Auth backend base client (attaches JWT, handles errors)
    │   ├── lmsApiClient.ts       LMS backend base client
    │   ├── announcementService.ts
    │   ├── eventService.ts
    │   ├── taskService.ts
    │   ├── taskScoreService.ts
    │   ├── userService.ts
    │   ├── lmsService.ts         Courses, enrollments
    │   ├── quizService.ts
    │   ├── forumService.ts
    │   ├── progressService.ts
    │   ├── analyticsService.ts
    │   ├── aiService.ts
    │   ├── youtubeService.ts
    │   └── youtubeTokenManager.ts
    │
    ├── store/
    │   └── UserContext.tsx       Global user state via React Context
    │
    ├── providers/
    │   └── MainProvider.tsx      Composes SessionProvider + UserContext + ThemeProvider
    │
    ├── types/                    All shared TypeScript interfaces
    │   ├── index.ts              Re-exports everything
    │   ├── user.ts, account.ts, announcement-event.ts, event.ts
    │   ├── course.ts, task.ts, calendar.ts
    │   ├── fill-blank.ts, form.ts
    │   └── (add new domain types here, re-export from index.ts)
    │
    ├── lib/
    │   ├── utils.ts              cn() helper (clsx + tailwind-merge)
    │   └── users/                api.ts, auth.ts, fileParser.ts, mappers.ts
    │
    ├── utils/                    Pure helpers — no React imports
    │   ├── calendar.ts, constants.ts, cookies.ts, dateUtils.ts
    │   ├── fillBlankUtils.ts, lms.ts, tokenManager.ts, utils.ts
    │
    ├── constants/index.ts        App-wide constants
    │
    └── assets/                   Static images/icons checked into repo
        └── bdclogo.png, bdclogo.ico
```

---

## 2. Environment Variables

### Runtime vs Build-time Split

Variables prefixed `NEXT_PUBLIC_` are **baked into the client bundle at build time** via Docker `ARG` → `ENV`. All others are server-only and never exposed to the browser.

```env
# ── Client-side (baked at build via Dockerfile ARG) ──────────────────────
NEXT_PUBLIC_API_URL=https://bdc.hpcc.vn/apiv1        # Used by service files in browser
NEXT_PUBLIC_LMS_API_URL=https://bdc.hpcc.vn/lmsapiv1 # Used by lmsApiClient in browser
NEXT_PUBLIC_YOUTUBE_UPLOAD_ENABLED=true

# ── Server-side only ──────────────────────────────────────────────────────
BACKEND_URL=http://backend:8080          # next.config.ts rewrites — Docker internal hostname
LMS_API_URL=http://lms-backend:8081      # next.config.ts rewrites — Docker internal hostname

NEXTAUTH_URL=https://bdc.hpcc.vn        # Must match actual domain — affects OAuth callbacks
NEXTAUTH_SECRET=<min 32 chars>

# ── YouTube OAuth (server-side Route Handlers only) ───────────────────────
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REDIRECT_URI=https://bdc.hpcc.vn/api/youtube/callback

# ── External integrations ─────────────────────────────────────────────────
GOOGLE_SCRIPT_URL=https://script.google.com/...   # Survey form → submit-form/route.ts
```

### When to use which approach

| Scenario | Correct approach |
|----------|-----------------|
| Client component fetching data | `NEXT_PUBLIC_API_URL` or `NEXT_PUBLIC_LMS_API_URL` via service files |
| Server Component or Route Handler | `process.env.BACKEND_URL` directly |
| Docker Compose (all services on same network) | `BACKEND_URL=http://backend:8080` (internal), proxied by `next.config.ts` |
| Local dev without Docker | `BACKEND_URL=http://localhost:8080`, `LMS_API_URL=http://localhost:8081` |

---

## 3. Proxy Rewrites (next.config.ts)

The frontend proxies all backend traffic through Next.js rewrites. **Never call backend ports directly from client code.**

| Frontend path | Proxies to | Purpose |
|---------------|-----------|---------|
| `/apiv1/:path*` | `BACKEND_URL/:path*` | Auth, users, events, announcements |
| `/uploads/:path*` | `BACKEND_URL/uploads/:path*` | Auth service uploads |
| `/lmsapiv1/:path*` | `LMS_API_URL/api/v1/:path*` | All LMS features |
| `/lmsapidocs/:path*` | `LMS_API_URL/:path*` | LMS Swagger |
| `/files/:path*` | `LMS_API_URL/api/v1/files/serve/:path*` | LMS files (1-year cache header) |

```ts
// Correct — proxy path, works in all environments
const res = await fetch(`/apiv1/announcements`);

// Wrong — hardcoded port, breaks in Docker and production
const res = await fetch(`http://localhost:8080/announcements`);
```

---

## 4. API Clients and Services

### 4.1 — Base Clients

Two base clients in `services/` handle JWT attachment and error normalisation. Every service file imports from one of them.

```
services/api.ts          →  Auth backend  (/apiv1/*)
services/lmsApiClient.ts →  LMS backend   (/lmsapiv1/*)
```

Both clients:
- Read the session token from NextAuth and attach `Authorization: Bearer <token>`
- Throw `Error` with a `.message` populated from the backend response body on non-2xx
- Return typed data — never raw `Response` objects

### 4.2 — Service File Template

One file per resource domain. Name it `<resource>Service.ts`.

```ts
// services/featureService.ts
import { apiClient } from "./api";   // swap to lmsApiClient for LMS resources
import type { Feature } from "@/types";

export const featureService = {
  getAll: (): Promise<Feature[]> =>
    apiClient.get("/features"),

  getById: (id: number): Promise<Feature> =>
    apiClient.get(`/features/${id}`),

  create: (data: Partial<Feature>): Promise<Feature> =>
    apiClient.post("/features", data),

  update: (id: number, data: Partial<Feature>): Promise<Feature> =>
    apiClient.put(`/features/${id}`, data),

  delete: (id: number): Promise<void> =>
    apiClient.delete(`/features/${id}`),
};
```

### 4.3 — Existing Services (do not duplicate)

| File | Resource |
|------|---------|
| `announcementService.ts` | Announcements — Auth backend |
| `eventService.ts` | Events — Auth backend |
| `taskService.ts` | Kanban tasks — Auth backend |
| `taskScoreService.ts` | Task scores |
| `userService.ts` | User management |
| `lmsService.ts` | Courses, enrollments — LMS backend |
| `quizService.ts` | Quizzes, attempts — LMS backend |
| `forumService.ts` | Forum posts & comments — LMS backend |
| `progressService.ts` | Student progress — LMS backend |
| `analyticsService.ts` | Analytics — LMS backend |
| `aiService.ts` | AI diagnosis, quiz generation |
| `youtubeService.ts` | YouTube upload |

---

## 5. Authentication

### In Client Components

```ts
import { useAuth } from "@/hooks/useAuth";

const { user, isAdmin, checkAdminAccess } = useAuth();

// Guard any admin mutation — shows alert and returns false if not admin
const handleSave = async () => {
  if (!checkAdminAccess()) return;
  await save();
};

// Guard with a custom Vietnamese action label (used in the alert message)
const handleDelete = async (id: number) => {
  if (!checkAdminAccess("xóa")) return;
  await remove(id);
};
```

### In Server Components / Route Handlers

```ts
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";

const session = await getServerSession(authOptions);
if (!session) {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}
```

### Global User Context

```ts
import { useContext } from "react";
import { UserContext } from "@/store/UserContext";

const { currentUser, setCurrentUser } = useContext(UserContext);
```

---

## 6. Hook Templates

### 6.1 — Resource Hook (CRUD + modal state)

Standard pattern — mirrors `useAnnouncements`, `useEvents`, `useTasks`.

```ts
// hooks/useFeature.tsx
import { useState, useEffect, useCallback } from "react";
import { featureService } from "@/services/featureService";
import type { Feature } from "@/types";

type ModalMode = "add" | "edit" | "view";
const EMPTY: Partial<Feature> = { title: "", description: "" };

export function useFeature() {
  const [items, setItems]     = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);

  const [modalOpen, setModalOpen]     = useState(false);
  const [modalMode, setModalMode]     = useState<ModalMode>("view");
  const [currentItem, setCurrentItem] = useState<Partial<Feature>>(EMPTY);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await featureService.getAll());
    } catch (err) {
      console.error("useFeature: fetch failed", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openModal = useCallback((mode: ModalMode, item?: Feature) => {
    setModalMode(mode);
    setCurrentItem(item ?? EMPTY);
    setModalOpen(true);
  }, []);

  const closeModal = useCallback(() => setModalOpen(false), []);

  const save = useCallback(async (item: Partial<Feature>) => {
    if (item.id) {
      await featureService.update(item.id, item);
    } else {
      await featureService.create(item);
    }
    closeModal();
    await load();
  }, [closeModal, load]);

  const remove = useCallback(async (id: number) => {
    await featureService.delete(id);
    setItems((prev) => prev.filter((f) => f.id !== id));
  }, []);

  return {
    items, loading,
    modalOpen, modalMode, currentItem, setCurrentItem,
    openModal, closeModal,
    save, remove,
  };
}
```

### 6.2 — Pagination Hook (existing — do not recreate)

```ts
// hooks/usePagination.tsx — already exists
const {
  visibleItems,  // T[]     — current displayed slice
  hasMore,       // boolean — controls ShowMoreButton visibility
  remaining,     // number  — count passed to ShowMoreButton
  showMore,      // () => void — expands by one page
} = usePagination(allItems, 4);   // 4 = items per page
```

---

## 7. Component Templates

### 7.1 — Display Card

```tsx
// components/dashboard/feature/FeatureCard.tsx
"use client";

import React from "react";
import type { Feature } from "@/types";

interface FeatureCardProps {
  item: Feature;
  isAdmin: boolean;
  onView: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export function FeatureCard({ item, isAdmin, onView, onEdit, onDelete }: FeatureCardProps) {
  return (
    <div
      className="bg-white dark:bg-slate-900 p-5 rounded-2xl
                 border border-slate-200 dark:border-slate-800
                 shadow-sm hover:shadow-md transition-shadow duration-300 cursor-pointer"
      onClick={onView}
    >
      <h3 className="text-lg font-bold text-slate-900 dark:text-slate-50 mb-1 line-clamp-1">
        {item.title}
      </h3>
      <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-2">
        {item.description}
      </p>

      {isAdmin && (
        <div className="flex gap-2 mt-4" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onEdit}
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 transition-colors"
          >
            Edit
          </button>
          <button
            onClick={onDelete}
            className="text-xs font-semibold text-red-500 hover:text-red-600 transition-colors"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
```

### 7.2 — List Component

```tsx
// components/dashboard/feature/FeatureList.tsx
"use client";

import React from "react";
import { LoadingState } from "@/components/dashboard/LoadingState";
import { FeatureCard } from "./FeatureCard";
import type { Feature } from "@/types";

interface FeatureListProps {
  items: Feature[];
  loading: boolean;
  isAdmin: boolean;
  onView: (item: Feature) => void;
  onEdit: (item: Feature) => void;
  onDelete: (id: number) => void;
}

export function FeatureList({ items, loading, isAdmin, onView, onEdit, onDelete }: FeatureListProps) {
  if (loading) return <LoadingState />;

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <p className="text-sm text-slate-400 dark:text-slate-600">No items found.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {items.map((item) => (
        <FeatureCard
          key={item.id}
          item={item}
          isAdmin={isAdmin}
          onView={() => onView(item)}
          onEdit={() => onEdit(item)}
          onDelete={() => onDelete(item.id)}
        />
      ))}
    </div>
  );
}
```

### 7.3 — Modal (Add / Edit / View — three modes, one component)

```tsx
// components/dashboard/modals/FeatureModal.tsx
"use client";

import React from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input }  from "@/components/ui/input";
import type { Feature } from "@/types";

type ModalMode = "add" | "edit" | "view";

interface FeatureModalProps {
  open: boolean;
  mode: ModalMode;
  item: Partial<Feature>;
  onOpenChange: (open: boolean) => void;
  onChange: (updated: Partial<Feature>) => void;
  onSave: () => void;
}

const TITLE: Record<ModalMode, string> = {
  add: "Add Item", edit: "Edit Item", view: "Item Details",
};

export function FeatureModal({ open, mode, item, onOpenChange, onChange, onSave }: FeatureModalProps) {
  const isReadOnly = mode === "view";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg bg-white dark:bg-slate-900
                                border border-slate-200 dark:border-slate-800 rounded-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-slate-900 dark:text-slate-50">
            {TITLE[mode]}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5 block">
              Title
            </label>
            <Input
              value={item.title ?? ""}
              disabled={isReadOnly}
              onChange={(e) => onChange({ ...item, title: e.target.value })}
              placeholder="Enter title..."
              className="rounded-xl border-slate-300 dark:border-slate-700
                         bg-slate-50 dark:bg-slate-800
                         focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500
                         transition-all duration-200"
            />
          </div>
          {/* Repeat this block for each additional field */}
        </div>

        {!isReadOnly && (
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="rounded-xl border-slate-300 dark:border-slate-700
                         text-slate-700 dark:text-slate-300
                         hover:bg-slate-50 dark:hover:bg-slate-800
                         active:scale-95 transition-all duration-200"
            >
              Cancel
            </Button>
            <Button
              onClick={onSave}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold
                         rounded-xl px-6 shadow-sm active:scale-95 transition-all duration-200"
            >
              {mode === "add" ? "Create" : "Save Changes"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

### 7.4 — LMS Shared Primitives

For any component inside `(learning)/lms/`, check the shared barrel first before building something new:

```tsx
import {
  Alert, Badge, Button, Card, CourseCard,
  EmptyState, Spinner, TabBar, StatCard,
  SectionHeader, ProgressBar, Divider, ContentTypeBadge,
} from "@/components/lms/shared";
```

These are **LMS-flavoured** variants intentionally separate from the dashboard design system. Do **not** use them in `(main)/` pages, and do **not** use dashboard components inside LMS pages.

---

## 8. Page Composition Pattern

`page.tsx` is a composition shell only — no business logic, no direct state, no fetching.

```tsx
// app/(main)/feature/page.tsx
"use client";

import React from "react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { SectionHeader }   from "@/components/dashboard/SectionHeader";
import { FeatureList }     from "@/components/dashboard/feature/FeatureList";
import { FeatureModal }    from "@/components/dashboard/modals/FeatureModal";
import { ShowMoreButton }  from "@/components/dashboard/ShowMoreButton";
import { useFeature }      from "@/hooks/useFeature";
import { usePagination }   from "@/hooks/usePagination";
import { useAuth }         from "@/hooks/useAuth";

export default function FeaturePage() {
  const { isAdmin, checkAdminAccess } = useAuth();

  const {
    items, loading,
    modalOpen, modalMode, currentItem, setCurrentItem,
    openModal, closeModal, save, remove,
  } = useFeature();

  const { visibleItems, hasMore, remaining, showMore } = usePagination(items, 4);

  const handleOpen = (mode: "add" | "edit" | "view", item?: Feature) => {
    if ((mode === "add" || mode === "edit") && !checkAdminAccess()) return;
    openModal(mode, item);
  };

  const handleSave = async () => {
    if (!checkAdminAccess()) return;
    try { await save(currentItem); }
    catch (e: any) { alert("Lỗi: " + e.message); }
  };

  const handleDelete = async (id: number) => {
    if (!checkAdminAccess("xóa")) return;
    try { await remove(id); }
    catch (e: any) { alert("Lỗi: " + e.message); }
  };

  return (
    <>
      {/* Modals outside the section — avoids z-index stacking issues */}
      <FeatureModal
        open={modalOpen}
        mode={modalMode}
        item={currentItem}
        onOpenChange={closeModal}
        onChange={setCurrentItem}
        onSave={handleSave}
      />

      <div className="space-y-10">
        <DashboardHeader />

        <section>
          <SectionHeader
            icon="📋"
            title="Feature Title"
            description="Short section description"
            showAddButton={isAdmin}
            onAdd={() => handleOpen("add")}
            addButtonText="Thêm mục"
          />
          <FeatureList
            items={visibleItems}
            loading={loading}
            isAdmin={isAdmin}
            onView={(item) => handleOpen("view", item)}
            onEdit={(item) => handleOpen("edit", item)}
            onDelete={handleDelete}
          />
          {hasMore && (
            <ShowMoreButton
              onClick={showMore}
              remaining={remaining}
              variant="announcement"
            />
          )}
        </section>
      </div>
    </>
  );
}
```

---

## 9. Types

All shared interfaces live in `src/types/`. Always add here and re-export from `index.ts`.

```ts
// types/feature.ts
export interface Feature {
  id: number;
  title: string;
  description: string;
  createdAt: string;   // ISO 8601 string from backend — use dateUtils.ts to display
  updatedAt: string;
  createdBy?: number;
}

// types/index.ts — add the export line
export * from "./feature";
```

Type discipline:
- `noImplicitAny: false` in tsconfig means TypeScript won't force-error on implicit `any` — but **always annotate explicitly anyway**
- Dates from backend arrive as ISO strings. Parse and format them with `utils/dateUtils.ts`
- Use `unknown` + type narrowing when the shape is genuinely uncertain — never cast to `any` as a shortcut

---

## 10. Styling Reference

### Approved Colour Tokens (Tailwind only — no custom colours without team approval)

| Role | Light | Dark |
|------|-------|------|
| Page background | `bg-slate-50` | `dark:bg-slate-950` |
| Card / sidebar bg | `bg-white` | `dark:bg-slate-900` |
| Card border | `border-slate-200` | `dark:border-slate-800` |
| Input bg | `bg-slate-50` | `dark:bg-slate-800` |
| Input border | `border-slate-300` | `dark:border-slate-700` |
| Heading text | `text-slate-900` | `dark:text-slate-50` |
| Body text | `text-slate-600` | `dark:text-slate-400` |
| Caption / subtext | `text-slate-500` | `dark:text-slate-500` |
| Placeholder | `text-slate-400` | `dark:text-slate-600` |
| Primary action | `bg-blue-600` | `dark:bg-blue-600` (unchanged) |
| Primary hover | `hover:bg-blue-700` | — |
| Danger | `text-red-500 bg-red-50` | `dark:text-red-400 dark:bg-red-950/40` |
| Success | `text-green-600 bg-green-50` | — |

### Fixed Typography Classes

```
H1 (page title):    text-3xl md:text-4xl font-extrabold text-slate-900 dark:text-slate-50 leading-tight
H2 (section title): text-2xl font-bold text-slate-900 dark:text-slate-50
H3 (card title):    text-lg font-bold text-slate-800 dark:text-slate-100
Body:               text-base text-slate-600 dark:text-slate-400 leading-relaxed
Caption:            text-sm text-slate-500 dark:text-slate-500
Tag / Badge label:  text-xs font-semibold text-blue-600 uppercase tracking-wider
```

### Copy-Paste Patterns

**Card:**
```tsx
<div className="bg-white dark:bg-slate-900 p-6 rounded-2xl
                border border-slate-200 dark:border-slate-800
                shadow-sm hover:shadow-md transition-shadow duration-300">
```

**Primary Button:**
```tsx
<Button className="bg-blue-600 hover:bg-blue-700 text-white font-semibold
                   rounded-xl px-6 py-2.5 shadow-sm
                   active:scale-95 transition-all duration-200">
```

**Outline Button:**
```tsx
<Button variant="outline"
        className="border border-slate-300 dark:border-slate-700
                   text-slate-700 dark:text-slate-300
                   hover:bg-slate-50 dark:hover:bg-slate-800
                   rounded-xl px-6 py-2.5
                   active:scale-95 transition-all duration-200">
```

**Input:**
```tsx
<Input className="rounded-xl border-slate-300 dark:border-slate-700
                  bg-slate-50 dark:bg-slate-800
                  text-slate-900 dark:text-slate-100
                  placeholder:text-slate-400 dark:placeholder:text-slate-600
                  focus:bg-white dark:focus:bg-slate-900
                  focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20
                  transition-all duration-200" />
```

**Loading state — always use the existing component:**
```tsx
import { LoadingState } from "@/components/dashboard/LoadingState";
<LoadingState />                        // default: "Đang tải..."
<LoadingState message="Loading..." />   // custom message
```

**Dark mode toggle — prevent hydration mismatch:**
```tsx
const { theme, setTheme } = useTheme();   // from next-themes via MainProvider
const [mounted, setMounted] = useState(false);
useEffect(() => setMounted(true), []);

{mounted && (theme === "dark"
  ? <Sun className="h-5 w-5" />
  : <Moon className="h-5 w-5" />
)}
```

---

## 11. Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Component file | `PascalCase.tsx` | `AnnouncementCard.tsx` |
| Hook file | `camelCase.tsx/.ts`, prefix `use` | `useAnnouncements.tsx` |
| Service file | `camelCase.ts`, suffix `Service` | `announcementService.ts` |
| Utility / helper | `camelCase.ts` | `dateUtils.ts` |
| Type file | `kebab-case.ts` | `announcement-event.ts` |
| Interface | `PascalCase` | `interface Announcement {}` |
| Prop interface | `{ComponentName}Props` | `interface AnnouncementCardProps {}` |
| Component export | Named — never default | `export function AnnouncementCard` |
| Page / layout | Default export (Next.js requirement) | `export default function DashboardPage` |
| Event handlers | Prefix `handle` | `handleSave`, `handleDelete`, `handleOpen` |
| Boolean state/props | Prefix `is` / `has` / `show` | `isAdmin`, `hasMore`, `showAddButton` |

---

## 12. Route Group Reference

| Route group | Layout | Who uses it | Auth required |
|-------------|--------|-------------|---------------|
| `(auth)` | Minimal, no sidebar | Unauthenticated users | No |
| `(landing)` | Public landing | Public visitors | No |
| `(main)` | Sidebar + MobileNav + Footer | All logged-in users | Yes |
| `(learning)/lms` | LMS shell layout | Students, teachers, LMS admins | Yes |

New authenticated page → `(main)/` inherits the sidebar automatically.
New LMS page → `(learning)/lms/` inherits the LMS layout automatically.

---

## 13. Adding a New Feature — Step-by-Step

1. **Type** — `src/types/<domain>.ts` → re-export from `types/index.ts`
2. **Service** — `src/services/<resource>Service.ts` using `api.ts` or `lmsApiClient.ts`
3. **Hook** — `src/hooks/use<Feature>.tsx` following the section 6.1 template
4. **Components** — `src/components/<area>/<feature>/` with Card + List + Modal files
5. **Page** — `src/app/(main)/<route>/page.tsx` or `(learning)/lms/<role>/<route>/page.tsx`
6. **Navigation** — add an entry to `src/components/layout/Sidebar.tsx` and `MobileNav.tsx`

---

## 14. Anti-Patterns

| Do not | Instead |
|--------|---------|
| Call `fetch()` inside a component or hook directly | Put it in `services/`, expose via a service function |
| Write data-fetching or state logic in `page.tsx` | Extract to a `use<Feature>()` hook |
| Use `any` type | Define an interface in `src/types/` |
| Use `lmsApiClient` from a `(main)/` component | `(main)/` uses `api.ts`; `(learning)/lms/` uses `lmsApiClient.ts` |
| Hardcode backend URLs or ports | Use proxy paths (`/apiv1/`, `/lmsapiv1/`) via service files |
| Use `backdrop-blur` on sidebar/navbar/layout | Glassmorphism is banned — use solid `bg-white dark:bg-slate-900` |
| Multi-colour gradients | Solid colours only, or same-hue light→dark |
| Inline styles (`style={{ color: "#333" }}`) | Tailwind utility classes only |
| Omit `dark:` counterpart on any colour class | Every bg, text, and border needs a dark-mode pair |
| Omit `active:scale-95` on interactive buttons | All clickable elements need press feedback |
| Leave `console.log` in committed code | Remove before PR |
| Use default export for a component | Named exports only (except `page.tsx` and `layout.tsx`) |
| Build a new LMS primitive | Check `components/lms/shared/` first |
| Use `NEXT_PUBLIC_*` vars for secrets | Secrets are server-only — never prefix with `NEXT_PUBLIC_` |

---

## 15. Pre-PR Checklist

- [ ] New type added to `src/types/` and re-exported from `index.ts`
- [ ] Service function calls `api.ts` or `lmsApiClient.ts` — no raw `fetch()` in hooks or components
- [ ] Hook follows the CRUD + modal pattern (section 6.1)
- [ ] Component in the correct folder with a named export
- [ ] Props interface named `<Component>Props`, fully typed, no `any`
- [ ] `page.tsx` is composition only — no `useState`, `useEffect`, or `fetch()` directly inside it
- [ ] All Tailwind colours from the approved token table (section 10)
- [ ] Every colour class has a `dark:` counterpart
- [ ] Buttons have `active:scale-95 transition-all duration-200`
- [ ] Cards use `rounded-2xl border-slate-200 dark:border-slate-800 shadow-sm`
- [ ] Inputs use `focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500`
- [ ] Loading uses `<LoadingState />` — no custom spinner invented
- [ ] Empty state handled with a visible message
- [ ] Admin-only mutations guarded with `checkAdminAccess()`
- [ ] No hardcoded localhost URLs or backend ports
- [ ] No `console.log` statements
- [ ] Renders correctly in both light mode and dark mode