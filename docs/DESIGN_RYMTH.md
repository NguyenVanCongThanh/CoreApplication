# BDC — Design Rhythm: Developer Guide

*Tài liệu chuẩn hóa UI/UX cho các dự án của Big Data Club (BDC). Mục tiêu: đồng bộ, chuyên nghiệp, tối ưu hóa hiệu suất đội Frontend.*

---

## 1. Triết lý thiết kế (Core Mindset)

* **Academic & Minimal** — giao diện mang tính học thuật, chuyên nghiệp và tinh giản; tránh phô trương.
* **Data-First** — nội dung (văn bản, số liệu) là nhân vật chính; UI là nền, dẫn dắt ánh nhìn.
* **Basic is the Best** — ưu tiên style cơ bản, sạch sẽ; hạn chế bóng đổ dày, viền kép, gradient rực rỡ.

---

## 2. Hệ thống màu sắc (Color System)

Sử dụng palette mặc định của Tailwind CSS — dưới đây là quy chuẩn và cách áp dụng. (Mẫu màu kèm swatch để dễ tham khảo.)

| Mục đích           |  Tailwind class |       Hex |                                                                                   Swatch                                                                                  |
| ------------------ | --------------: | --------: | :-----------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
| Primary background |   `bg-blue-600` | `#2563eb` | <span style="display:inline-block;width:1.2em;height:1.2em;background:#2563eb;border-radius:4px;border:1px solid #0000001a;vertical-align:middle;margin-left:6px"></span> |
| Primary hover      |   `bg-blue-700` | `#1d4ed8` | <span style="display:inline-block;width:1.2em;height:1.2em;background:#1d4ed8;border-radius:4px;border:1px solid #0000001a;vertical-align:middle;margin-left:6px"></span> |
| Accent text / link | `text-blue-600` | `#2563eb` | <span style="display:inline-block;width:1.2em;height:1.2em;background:#2563eb;border-radius:4px;border:1px solid #0000001a;vertical-align:middle;margin-left:6px"></span> |
| Light primary bg   |    `bg-blue-50` | `#eff6ff` | <span style="display:inline-block;width:1.2em;height:1.2em;background:#eff6ff;border-radius:4px;border:1px solid #0000001a;vertical-align:middle;margin-left:6px"></span> |

**Neutral (Slate)** — ưu tiên Slate để tạo cảm giác công nghệ, hiện đại:

| Purpose           |              Class |       Hex |
| ----------------- | -----------------: | --------: |
| Page background   |      `bg-slate-50` | `#f8fafc` |
| Card background   |         `bg-white` | `#ffffff` |
| Card border       | `border-slate-200` | `#e2e8f0` |
| Input border      | `border-slate-300` | `#cbd5e1` |
| Heading text      |   `text-slate-900` | `#0f172a` |
| Body text         |   `text-slate-600` | `#475569` |
| Caption / subtext |   `text-slate-500` | `#64748b` |
| Placeholder       |   `text-slate-400` | `#94a3b8` |

**Semantic colors** (áp dụng cho trạng thái):

* Danger / Error: `text-red-500`, `bg-red-50`, `border-red-500`.
* Success: `text-green-600`, `bg-green-50`.
* Warning: `text-yellow-600`, `bg-yellow-50`.

---

## 3. Typography (Phân cấp & class chuẩn)

Đặt các class cố định để người dùng dễ scan thông tin.

* **H1 — Page Title**
  `class="text-3xl md:text-4xl font-extrabold text-slate-900 leading-tight"`

* **H2 — Section Title**
  `class="text-2xl font-bold text-slate-900"`

* **H3 — Card / Item Title**
  `class="text-lg font-bold text-slate-800"`

* **Body Text**
  `class="text-base text-slate-600 leading-relaxed"`

* **Subtext / Caption**
  `class="text-sm text-slate-500"`

* **Tag / Label**
  `class="text-xs font-semibold text-blue-600 uppercase tracking-wider"`

**Nguyên tắc:** luôn dùng kích thước, trọng số, màu cố định cho từng vai trò; tránh đặt style tùy tiện trong từng component.

---

## 4. UI Components — Mẫu code tái sử dụng

### 4.1 Cards & Containers

Giữ viền mảnh, bo góc lớn, shadow nhẹ.

```jsx
<div className="bg-white p-6 md:p-8 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-300">
  <h3 className="text-lg font-bold text-slate-900 mb-2">Tiêu đề Card</h3>
  <p className="text-slate-600">Nội dung của thẻ nằm ở đây.</p>
</div>
```

### 4.2 Inputs & Forms

Focus: viền blue + ring nhẹ. Lỗi: viền đỏ + nền đỏ nhạt.

```jsx
{/* Input chuẩn */}
<input 
  className="w-full border border-slate-300 rounded-xl p-3.5 text-slate-900 placeholder:text-slate-400 bg-slate-50
             focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
  placeholder="Nhập dữ liệu..."
/>

{/* Input lỗi */}
<input 
  className="w-full border border-red-500 rounded-xl p-3.5 text-slate-900 placeholder:text-red-300 bg-red-50
             focus:outline-none focus:ring-2 focus:ring-red-500/20 transition-all"
  placeholder="Dữ liệu không hợp lệ..."
/>
```

**Nguyên tắc form:**

* Luôn show trạng thái (focus, error, disabled) rõ ràng.
* Validation messages nhỏ, đặt sát input, dùng `text-sm text-red-500`.

### 4.3 Buttons

Padding nhất quán; transition; active scale nhỏ.

```jsx
{/* Primary */}
<button className="bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl px-6 py-3 shadow-sm transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed">
  Hoàn tất gửi
</button>

{/* Secondary */}
<button className="bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 hover:border-slate-400 rounded-xl px-6 py-3 font-medium shadow-sm transition-all active:scale-95">
  Quay lại
</button>

{/* Ghost */}
<button className="bg-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl px-4 py-2 font-medium transition-all">
  Hủy bỏ
</button>
```

---

## 5. Spacing, Layout & Animation

* **Wrapper (toàn trang):** `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8` (hoặc `max-w-4xl` cho form/bài viết).
* **Section spacing:** `py-20` hoặc `py-24` để tạo breathing space.
* **Grid / Flex gaps:** `gap-4`, `gap-6`, `gap-8`.
* **Transitions:** `transition-all duration-200` hoặc `duration-300`.
* **Entrance animation (scroll):** từ `opacity-0 translate-y-8` → `opacity-100 translate-y-0` với `duration-700`. (Dùng chỉ cho các element trọng yếu để tránh chi phí reflow.)

---

## 6. Anti-Patterns — Tuyệt đối tránh

1. **Glassmorphism diện rộng:** tránh `backdrop-blur` + nền trong suốt cho layout chính.
2. **Viền kép / bo góc gắt:** không dùng `border-double`, `border-black` dày; ưu tiên `rounded-xl` / `rounded-2xl` và `border-slate-200`.
3. **Căn giữa đoạn văn dài:** chỉ tiêu đề được phép `text-center`; đoạn mô tả ≥3 dòng phải `text-left`.
4. **Gradient rực rỡ:** không dùng gradient nhiều màu (ví dụ: hồng→tím→vàng) cho viền hoặc progress. Chỉ dùng solid hoặc cùng dải (nhạt→đậm).
5. **Hardcode data:** nội dung cấu trúc, câu hỏi form, danh sách phải nằm trong `.json` hoặc API; UI chỉ render.

---

## 7. Checklist triển khai nhanh (Developer)

* [ ] Dùng palette Tailwind đã chuẩn hóa; không thêm màu mới nếu không có approval.
* [ ] Áp dụng typography classes cố định cho mọi page/component.
* [ ] Inputs: focus → `ring-blue-500/20`; error → `border-red-500` + `bg-red-50`.
* [ ] Buttons: padding `px-6 py-3` cho primary; `transition-all` + `active:scale-95`.
* [ ] Cards: `rounded-2xl`, `border-slate-200`, `shadow-sm`.
* [ ] Không hardcode data; tách data ra `.json`/API.
* [ ] Review accessibility: đủ contrast, keyboard focus visible, aria labels với form controls.
