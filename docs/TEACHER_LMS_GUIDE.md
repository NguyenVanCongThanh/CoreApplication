# Teacher LMS Guide

| Field     | Value                              |
|-----------|------------------------------------|
| Version   | 2.0.0                              |
| Status    | Approved                           |
| Date      | 2026-04-06                         |
| Authors   | BDC Frontend Team                  |
| Reviewers | BDC Lead Dev                       |

## Revision History

| Version | Date       | Author          | Description                                      |
|---------|------------|-----------------|--------------------------------------------------|
| 1.0.0   | 2026-02-01 | BDC Team        | Initial draft, single-page tabs                  |
| 2.0.0   | 2026-04-06 | BDC Team        | Route-per-tab refactor, breadcrumb nav, ContentModal split |

---

## 1. Architecture Overview

```
/lms/teacher/                        Teacher area root
├── page.tsx                         Dashboard
├── layout.tsx                       Sticky header + nav links
│
└── courses/
    ├── page.tsx                     Course list
    ├── create/page.tsx              Create course form
    │
    └── [courseId]/
        ├── layout.tsx               Course header + tab nav (breadcrumb)
        ├── page.tsx                 Redirect → overview
        ├── overview/page.tsx        Course details + sections list
        ├── content/page.tsx         Section/content tree
        ├── learners/page.tsx        Enrolled learners
        ├── students/page.tsx        Per-student progress table
        └── ai/page.tsx              AI quiz gen + heatmap
```

Navigation flow:

```
  Dashboard (/lms/teacher)
      |
      +-- Courses list (/lms/teacher/courses)
            |
            +-- Create course (/lms/teacher/courses/create)
            |
            +-- Course detail (/lms/teacher/courses/{id})
                  |
          +-------+--------+----------+----------+------+
          |       |        |          |          |      |
       Overview Content Learners  Students     AI    (tabs)
```

Breadcrumb pattern on each tab:

```
[Dashboard icon] > Khóa học > [Course title] > [Tab name]
```

Every segment except the last is a clickable link.

---

## 2. Route Reference

### 2.1 Dashboard

**Route:** `/lms/teacher`

**Purpose:** Entry point after role selection. Shows greeting, high-level stats,
quick action cards, and a list of the most recently modified courses.

**Features:**

- Greeting by time of day (buổi sáng / chiều / tối).
- Stats row: total courses, published count, total accepted students.
- Quick action cards: Create course, Manage courses, Analytics.
- Recent courses list (last 6 by creation date) with inline settings shortcut.
- Refresh button to reload all data without a page reload.
- "Đổi vai trò" button clears sessionStorage and returns to `/lms` role selector.

**Data sources:**

```
GET /lmsapiv1/courses/my?page_size=100      → all teacher courses
GET /lmsapiv1/courses/{id}/learners?status=ACCEPTED  → accepted students (first 10 courses)
```

---

### 2.2 Course List

**Route:** `/lms/teacher/courses`

**Purpose:** Full list of all courses owned by the authenticated teacher.

**Features:**

- Status filter tabs: All / Published / Draft (with live counts).
- Client-side search by title and description.
- Per-row publish toggle (DRAFT → PUBLISHED only).
- Per-row delete with confirmation dialog.
- Clicking a row navigates to the course detail overview page.
- Empty state with CTA to create first course.

**Data sources:**

```
GET  /lmsapiv1/courses/my?status={PUBLISHED|DRAFT}&page_size=200
POST /lmsapiv1/courses/{id}/publish
DEL  /lmsapiv1/courses/{id}
```

---

### 2.3 Create Course

**Route:** `/lms/teacher/courses/create`

**Purpose:** Form to create a new course in DRAFT status.

**Fields:**

| Field          | Required | Notes                                   |
|----------------|----------|-----------------------------------------|
| Title          | Yes      | 3–255 characters                        |
| Description    | No       | Up to 5,000 characters                  |
| Category       | No       | Free-text dropdown                      |
| Level          | No       | BEGINNER / INTERMEDIATE / ADVANCED      |
| Thumbnail URL  | No       | Must be a valid URL if provided         |

**Behaviour on success:** Navigates directly to the course detail page
(`/lms/teacher/courses/{newId}/overview`).

---

### 2.4 Course Detail — Shared Layout

**Route:** `/lms/teacher/courses/[courseId]/*`

**Purpose:** Persistent wrapper rendered across all five course tabs.
Does not re-mount between tab navigations.

**Persistent elements:**

```
+----------------------------------------------------------+
|  [Dashboard] > Khóa học > [Course title] > [Tab]        | <- breadcrumb
+----------------------------------------------------------+
|  [Draft/Published badge]  [Category]  [Level]           |
|  Course title (H1)                      [Chỉnh sửa btn] |
|  Description (line-clamped to 1 line)                   |
+----------------------------------------------------------+
|  Tổng quan | Nội dung | Học viên | Tiến độ | 🤖 AI       | <- tab nav
+----------------------------------------------------------+
|                                                          |
|  {children}  (tab page content)                         |
|                                                          |
+----------------------------------------------------------+
```

**Edit course modal** is triggered from the Chỉnh sửa button in the layout
header; it is available from any tab.

---

### 2.5 Overview Tab

**Route:** `/lms/teacher/courses/[courseId]/overview`

**Purpose:** At-a-glance summary of the course configuration and structure.

**Features:**

- Publish call-to-action banner (shown only when course status is DRAFT).
- Details grid: Status, Level, Category, Number of sections.
- Ordered sections list showing each section's title and description.

**When to use:** Review overall course structure before publishing, or after a
bulk content upload to verify everything looks right.

---

### 2.6 Content Tab

**Route:** `/lms/teacher/courses/[courseId]/content`

**Purpose:** Full section → content tree editor.

**Features:**

- Collapsible section rows with index badge.
- Per-section actions: Add content (+ button), Bulk upload, Edit, Delete.
- Per-content actions (shown on hover): Preview, Edit, Delete.
- Content type badge on each row (VIDEO / DOCUMENT / QUIZ / etc.).
- Mandatory badge for content flagged as is_mandatory.
- AI Index button on each indexable content item (TEXT / DOCUMENT / VIDEO / IMAGE):
  - States: not_indexed → processing → indexed / failed.
  - Polling every 4 seconds while processing.
  - Re-index available for already-indexed content.

**ContentModal architecture (refactored):**

```
ContentModal.tsx  (orchestrator)
  ├── TextContentForm          → Markdown editor
  ├── VideoContentForm         → YouTube | Server | URL tabs
  ├── DocumentContentForm      → File upload (PDF, Word…)
  ├── ImageContentForm         → File upload or external URL
  ├── QuizContentForm          → QuizSettingsForm wrapper
  └── ForumAnnouncementForm    → Info card, no upload needed
```

Each form component is under `components/lms/teacher/content-forms/`.
Adding a new content type means creating one new file and registering it
in ContentModal's switch statement.

**BulkUploadModal:** Accepts drag-and-drop of multiple files simultaneously.
Auto-detects type from extension.  Each file gets its own title/description
field and a mandatory toggle.  Uploads are sequential with per-file status
badges (Chờ / Đang tải / Thành công / Lỗi).

---

### 2.7 Learners Tab

**Route:** `/lms/teacher/courses/[courseId]/learners`

**Purpose:** View the list of students who have enrolled in the course.

**Features:**

- Filter tabs: All / Đã duyệt / Từ chối.
- Mini stat card showing accepted count.
- List rows showing: avatar initial, name, email, status badge.

**Note:** Enrollment approval/rejection is currently performed from the
admin panel.  This tab is read-only for teachers.

---

### 2.8 Students Progress Tab

**Route:** `/lms/teacher/courses/[courseId]/students`

**Purpose:** Detailed per-student progress monitoring.

**Features:**

- Summary bar (4 cards): total students, average progress %, quiz average, at-risk count.
- Sortable table with columns: Student name, Progress bar, Quiz avg, Last activity, Status tag.
- Click any row to open an inline detail panel on the right:
  - Profile (avatar, name, email, last activity).
  - Mandatory progress bar with completed / remaining count.
  - Quiz average score with colour coding (≥70 % green, <70 % amber).
  - Alert banners for <20 % progress or 100 % completion.
  - "Liên hệ học viên" mailto link.
- Live search filters the table by name or email.
- Refresh button re-fetches the analytics endpoint.

**Status tags:**

| Tag         | Condition                           |
|-------------|-------------------------------------|
| Cần chú ý   | progress_percent < 20 and total_mandatory > 0 |
| Hoàn thành  | progress_percent == 100             |
| Đang học    | progress_percent > 0                |
| Chưa bắt đầu| progress_percent == 0               |

---

### 2.9 AI Tab

**Route:** `/lms/teacher/courses/[courseId]/ai`

**Purpose:** Two AI-powered features: quiz question generation from course
content, and a class-level knowledge-gap heatmap.

#### 2.9.1 AIQuizGenPanel

Three sub-tabs (Nodes / Tạo mới / Chờ duyệt):

**Nodes sub-tab:**
- Displays the AI knowledge graph (force-directed graph or list view toggle).
- Each node represents a topic extracted from indexed content.
- Click a graph node to open a side panel with: description, connected edges,
  and the raw source text chunks that grounded the node (verifiability panel).
- Add node form: English name, Vietnamese name, description, optional parent.
- "📎 Liên kết" button on each node opens ContentPickerModal to associate a
  document or video with the node so the AI has source material.

**Tạo mới sub-tab:**
- Select a knowledge node as the topic.
- Select Bloom taxonomy levels (checkboxes): Nhớ / Hiểu / Áp dụng / Phân tích / Đánh giá / Sáng tạo.
- Select language: Tiếng Việt or English.
- "Tạo X câu hỏi với AI" button calls the RAG-based quiz generation endpoint.
- Generated questions go to the Chờ duyệt queue.

**Chờ duyệt sub-tab:**
- Lists all generated questions with status: Chờ duyệt / Đã duyệt / Từ chối.
- Expand any card to see answer options, correct answer, explanation, and
  the source quote from the document.
- Approve: opens QuizSelectorModal to pick which quiz to add the question to.
- Reject: requires a reason note.

#### 2.9.2 AIHeatmapSection

- Grid of coloured cells, one per knowledge node.
- Colour encodes wrong rate: green (≤10 %) → yellow → orange → red (>60 %).
- Hover tooltip shows: node name, wrong/total answers, student count, mastery label.
- "Cần ôn tập ngay" panel lists the top 3 weakest nodes (wrong rate > 30 %).
- Refresh button re-fetches from the class heatmap endpoint.

---

### 2.10 Quiz Management

**Route:** `/lms/teacher/quiz/[quizId]/manage`

**Purpose:** Add, edit, and delete questions for a specific quiz.

**Features:**

- Quiz stats row: question count, total points, time limit, publish status.
- Question list with type badge, points badge, image count badge.
- Per-question actions: Edit (opens modal), Delete (with confirm).
- Add question modal supports all types:
  - SINGLE_CHOICE / MULTIPLE_CHOICE: answer options with correct radio/checkbox.
  - SHORT_ANSWER: optional correct answers with case-sensitive and exact-match flags.
  - ESSAY / FILE_UPLOAD: no correct answers (teacher grades manually).
  - FILL_BLANK_TEXT / FILL_BLANK_DROPDOWN: FillBlankTextEditor / FillBlankDropdownEditor.
- After saving a new question, modal stays open to allow adding images (QuestionImageUploader).
- Quiz settings modal (⚙️ Cài đặt Quiz): time limit, max attempts, passing score,
  shuffle, auto-grade, show results, allow review, publish toggle.
- "✓ Chấm bài" button navigates to the grading page.

---

### 2.11 Quiz Grading

**Route:** `/lms/teacher/quiz/[quizId]/grading`

**Purpose:** Manual grading of essay, file upload, and short-answer responses.

**Features:**

- Stats: total answers, graded count, ungraded count.
- Filter panel: graded status / student search / question type.
- Answer cards showing: student name, email, submission time, question text, student answer.
- For FILE_UPLOAD: displays file name, size, and a download link.
- Grading form: points input (max shown), feedback textarea, Save and Cancel.
- After grading, the card updates in-place without a full page reload.

---

## 3. Component Map

```
components/lms/teacher/
│
├── BreadcrumbNav.tsx               Reusable breadcrumb (all teacher pages)
│
├── tabs/
│   ├── ContentTab.tsx              Section/content tree (used by content/page.tsx)
│   └── LearnersTab.tsx             Learner list (used by learners/page.tsx)
│
├── content-forms/
│   ├── types.ts                    ContentFormState + ContentFormProps interfaces
│   ├── TextContentForm.tsx         Markdown editor
│   ├── VideoContentForm.tsx        YouTube / Server / URL tabs
│   ├── FileContentForms.tsx        DocumentContentForm + ImageContentForm
│   ├── QuizContentForm.tsx         QuizSettingsForm wrapper
│   └── ForumAnnouncementContentForm.tsx  Info card
│
├── ContentModal.tsx                Orchestrator (uses content-forms/)
├── EditContentModal.tsx            Edit existing content
├── BulkUploadModal.tsx             Multi-file drag-and-drop upload
├── EditCourseModal.tsx             Edit course title / description / level
├── SectionModal.tsx                Create or edit a section
├── ContentPickerModal.tsx          Pick a document/video to link to an AI node
├── QuizSelectorModal.tsx           Pick a quiz when approving an AI question
│
├── AIQuizGenPanel.tsx              Knowledge nodes + quiz generation + draft review
├── AIIndexButton.tsx               Per-content AI indexing button with polling
├── AINodeManager.tsx               Knowledge node CRUD + graph view
├── KnowledgeGraph.tsx              Force-directed graph (react-force-graph-2d)
│
├── OverviewTab.tsx                 Course detail grid + sections list
├── StudentTab.tsx                  StudentsTab: progress table + inline detail
│
└── students/
    ├── StudentSummaryBar.tsx       4-card stats bar
    ├── StudentProgressTable.tsx    Sortable table with progress bars
    └── StudentDetailPanel.tsx      Fixed side panel (used by StudentsTab)
```

---

## 4. Teacher Workflows

### Workflow 1 — Creating a New Course from Scratch

```
Step 1   Navigate to /lms/teacher/courses
Step 2   Click "Tạo khóa học mới"
Step 3   Fill in title (required), description, category, level
Step 4   Submit → redirected to overview tab
Step 5   Navigate to Content tab
Step 6   Click "Thêm chương" → fill title + order index → Tạo chương
Step 7   Inside the new section, click + to add content
Step 8   Choose type, fill title, upload file or write text
Step 9   Repeat steps 6-8 for all chapters and lessons
Step 10  Return to Overview tab → click "Xuất bản ngay"
Step 11  Share the course URL with students or use bulk-enroll
```

```
  /courses             /courses/create          /courses/{id}/overview
      |                     |                         |
  [Create btn] -----------> [Form] ----------------> [Publish banner]
                                                      |
                                               [Xuất bản ngay]
                                                      |
                                             Status: PUBLISHED
```

---

### Workflow 2 — Preparing AI Quiz Generation

Before the AI can generate grounded questions, indexed content must be linked
to knowledge nodes. The sequence is:

```
Step 1   Go to AI tab → Nodes sub-tab
Step 2   Click "Thêm Node" → fill name (EN), Vietnamese name, description
Step 3   On the new node row, click "📎 Liên kết"
Step 4   ContentPickerModal opens → select a DOCUMENT or VIDEO from the course
Step 5   The selected content is processed and chunked by the AI service
Step 6   Node status changes to "Có tài liệu" (chunk_count > 0)
Step 7   Switch to "Tạo mới" sub-tab
Step 8   Select the node → select Bloom levels → click "Tạo X câu hỏi"
Step 9   Switch to "Chờ duyệt" sub-tab
Step 10  Review each generated question → Approve (select target quiz) or Reject
```

```
  AI tab: Nodes
      |
      +-- [Thêm Node] → node created with chunk_count = 0
      |
      +-- [📎 Liên kết] → ContentPickerModal → select DOCUMENT
      |                                            |
      |                                    AI service processes file
      |                                    node.chunk_count > 0
      v
  AI tab: Tạo mới
      |
      +-- Select node + Bloom levels → [Tạo X câu hỏi]
                                            |
                                    draft questions created
                                            |
  AI tab: Chờ duyệt                         v
      |
      +-- Review each card → [Duyệt] → QuizSelectorModal → question added to quiz
```

**Important:** Content must be AI-indexed before linking to a node.
Use the AI Index button (brain icon) on each content item in the Content tab.

---

### Workflow 3 — Monitoring Student Progress

```
Step 1   Navigate to course → Students tab
Step 2   Review summary bar (average progress, quiz avg, at-risk count)
Step 3   Sort table by progress_percent ascending to find lowest-progress students
Step 4   Click a row to open the detail panel
Step 5   For students with progress < 20 % → click "Liên hệ học viên" to send email
Step 6   Switch to AI tab → scroll to Heatmap section to identify weak knowledge areas
Step 7   Create additional content or quiz questions targeting those weak areas
```

```
  Students tab
      |
      +-- Summary bar: 3 học viên cần chú ý (progress < 20%)
      |
      +-- Sort by progress ASC → identify bottom students
      |
      +-- Click row → detail panel → [Liên hệ học viên]
      |
      +-- AI tab → Heatmap: "Recursion" node is red (65% wrong)
      |
      +-- Content tab → Add new TEXT lesson on Recursion
      +-- AI tab → Tạo mới → generate quiz questions on Recursion node
```

---

### Workflow 4 — Grading Essay Responses

```
Step 1   In the Content tab, identify the QUIZ content item
Step 2   Click Edit → Quản lý Quiz button
Step 3   On the quiz manage page, click "✓ Chấm bài"
Step 4   On the grading page, filter by "Chưa chấm"
Step 5   For each answer card: review student answer
Step 6   Click "Chấm điểm" → enter points and feedback
Step 7   Click "Lưu điểm"
Step 8   Repeat for all ungraded submissions
```

```
  Content tab
      |
  [Quiz item] → [Edit] → [Quản lý Quiz]
                               |
                         [✓ Chấm bài]
                               |
                     Grading page
                               |
                  Filter: Chưa chấm (N answers)
                               |
                  For each:  [Chấm điểm] → enter score + feedback → [Lưu]
```

---

### Workflow 5 — Bulk Content Upload

Use this when you have a folder of files (slides, PDFs, recordings) to add to a section all at once.

```
Step 1   Go to Content tab
Step 2   On the target section header, click the Upload icon (⬆)
Step 3   BulkUploadModal opens
Step 4   Drag and drop all files, or click "Chọn file"
Step 5   For each file: review auto-detected title, edit if needed
Step 6   Toggle "Nội dung bắt buộc" for files students must complete
Step 7   Click "✓ Tải lên tất cả"
Step 8   Each file uploads sequentially with per-file status badges
Step 9   Click Đóng → section expands automatically showing new content
```

---

## 5. Data Flow Diagram

```
  Browser (Teacher)
       |
       | HTTPS
       v
  Next.js frontend (/lms/teacher/*)
       |
       | HTTP (proxy via /lmsapiv1/*)
       | Authorization: Bearer <JWT>  (added by middleware.ts)
       v
  LMS Service (Go :8081)
       |
       +-- /courses/*         Course + section + content CRUD
       +-- /enrollments/*     Enrollment management
       +-- /quizzes/*         Quiz + question + attempt management
       +-- /ai/*              Proxied to AI service
       |
       |  HTTP :8000
       v
  AI Service (FastAPI + Celery :8000)
       |
       +-- /generate-quiz     RAG-grounded question generation
       +-- /heatmap           Class-level knowledge gap analysis
       +-- /index             Document/video chunking + embedding
```

---

## 6. Environment Notes

The teacher layout validates `sessionStorage.lms_selected_role` on mount.
If the stored role is not `TEACHER` or `ADMIN`, the user is redirected to
`/lms` for role re-selection.  This check runs in `teacher/layout.tsx`
before any data is fetched.

The AI features require `ai-service` to be running and reachable by
`lms-service`.  If the service is unavailable, the AI tab shows an amber
warning banner rather than crashing.

---

## 7. Checklist Before Publishing a Course

```
[ ] Course has a clear title and description
[ ] At least one section exists
[ ] Every section has at least one content item
[ ] Mandatory content items are correctly flagged (is_mandatory = true)
[ ] All DOCUMENT and VIDEO content items have been AI-indexed (for AI features)
[ ] At least one QUIZ exists if the course has graded activities
[ ] Quiz is published (is_published = true) so students can take it
[ ] Overview tab reviewed — level, category, and section order are correct
[ ] Students tab shows 0 enrolled (expected for a brand new course)
```
