# Module Tính Điểm Task - Hướng Dẫn Sử Dụng

## Tính Năng Chính

Module này cho phép Admin và Manager:
1. **Thêm/cập nhật điểm** cho các thành viên tham gia task
2. **Áp dụng điểm** - cộng điểm vào `totalScore` của user sau khi hoàn thành task
3. **Trừ điểm riêng** - trừ điểm từ từng thành viên với lý do cụ thể
4. **Huỷ áp dụng điểm** - loại bỏ điểm đã cộng
5. **Xoá bản ghi điểm** - xoá hoàn toàn một bản ghi điểm
6. **Khởi tạo điểm hàng loạt** - tự động tạo điểm cho tất cả assignees
7. **Hoàn thành task** - chuyển task sang "Done" và cộng điểm tự động

## Backend Architecture

### Models
- **TaskScore** (`com.example.demo.model.TaskScore`)
  - Lưu điểm của mỗi user cho mỗi task
  - Track thời gian cộng điểm (appliedAt)
  - Lưu ghi chú lý do (notes)
  - Unique constraint: (task_id, user_id) chỉ có một bản ghi

### Repository
- **TaskScoreRepository** (`com.example.demo.repository.TaskScoreRepository`)
  - CRUD operations
  - Query tìm score theo task/user
  - Query tổng điểm đã áp dụng của user

### Service
- **TaskScoreService** (`com.example.demo.service.TaskScoreService`)
  - `setScore()` - Thêm/cập nhật điểm
  - `deductScore()` - Trừ điểm
  - `applyScoresToTask()` - Cộng điểm cho tất cả assignees
  - `toggleApplyScore()` - Bật/tắt áp dụng điểm cho user
  - `deleteScore()` - Xoá bản ghi điểm
  - `initializeScoresForTask()` - Khởi tạo điểm cho tất cả assignees
  - `completeTaskAndApplyScores()` - Hoàn thành task và cộng điểm
  - **Tất cả các method đều validate rằng user là ADMIN hoặc MANAGER**

### Controller
- **TaskScoreController** (`com.example.demo.controller.TaskScoreController`)

#### Endpoints

```
GET /api/task-scores/{taskId}/{userId}
  Lấy điểm của một user cho một task
  Trả về: TaskScoreResponse

GET /api/task-scores/task/{taskId}
  Lấy tất cả điểm của một task
  Trả về: List<TaskScoreResponse>

GET /api/task-scores/user/{userId}
  Lấy tất cả điểm của một user
  Trả về: List<TaskScoreResponse>

GET /api/task-scores/user/{userId}/total
  Lấy tổng điểm đã áp dụng của một user
  Trả về: { totalScore: number }

POST /api/task-scores/set?adminUserId={userId}
  Thêm/cập nhật điểm
  Request body:
  {
    "taskId": 1,
    "userId": 2,
    "score": 10,
    "notes": "Good work"
  }
  Trả về: TaskScoreResponse

PATCH /api/task-scores/{taskId}/{userId}/deduct?deductAmount=5&reason=Late&adminUserId={userId}
  Trừ điểm cho user
  Trả về: TaskScoreResponse

POST /api/task-scores/{taskId}/apply?adminUserId={userId}
  Cộng điểm cho tất cả assignees
  Trả về: List<TaskScoreResponse>

PATCH /api/task-scores/{taskId}/{userId}/toggle?applied=true&adminUserId={userId}
  Bật/tắt áp dụng điểm
  Trả về: TaskScoreResponse

DELETE /api/task-scores/{taskId}/{userId}?adminUserId={userId}
  Xoá bản ghi điểm
  Trả về: { message: "Score deleted successfully" }

POST /api/task-scores/{taskId}/initialize?initialScore=10&adminUserId={userId}
  Khởi tạo điểm cho tất cả assignees
  Trả về: List<TaskScoreResponse>

POST /api/task-scores/{taskId}/complete?adminUserId={userId}
  Hoàn thành task và cộng điểm
  Trả về: List<TaskScoreResponse>
```

## Frontend Architecture

### Services
- **taskScoreService** (`src/services/taskScoreService.ts`)
  - Wrapper để gọi các API endpoints
  - Các method: `setScore()`, `deductScore()`, `applyScoresToTask()`, v.v.

### Hooks
- **useTaskScores** (`src/hooks/useTaskScores.tsx`)
  - Custom hook để quản lý state score
  - Loading, error handling
  - Các function để fetch/update scores

### Components
- **TaskScoreModal** (`src/components/Board/Task/TaskScoreModal.tsx`)
  - Modal để quản lý điểm cho một task
  - Hiển thị tất cả assignees với score của họ
  - Cho phép:
    - Set score
    - Apply/unapply score
    - Deduct score (với lý do)
    - Delete score
    - Initialize scores cho task
    - Apply all scores cùng lúc

### Updated Components
- **TaskCard** - Thêm button "Manage Scores" trong menu
- **BoardColumn** - Pass `onOpenScore` callback
- **page.tsx (tasks)** - Thêm `scoreModalState` và handlers

### Types
- **TaskScore** (in `src/types.ts`)
  ```typescript
  type TaskScore = {
    id?: number;
    taskId?: number;
    taskTitle?: string;
    userId?: number;
    userName?: string;
    userEmail?: string;
    userCode?: string;
    score: number;
    applied?: boolean;
    scoredById?: number;
    scoredByName?: string;
    scoredAt?: string;
    appliedAt?: string;
    notes?: string;
  }
  ```

## Quy Trình Sử Dụng

### Scenario 1: Set điểm cho task
1. Admin/Manager mở task, click "Manage Scores"
2. Click "Initialize Scores" để tạo bản ghi cho tất cả assignees
3. Nhập điểm khởi tạo (e.g., 10 points)
4. Hệ thống tự động tạo bản ghi với score=10 cho mỗi assignee
5. Để chỉnh điểm, click "Edit" trên dòng assignee
6. Nhập điểm mới, click Save

### Scenario 2: Áp dụng điểm sau khi hoàn thành task
1. Sau khi set score, click "Apply All Scores"
2. Hệ thống tự động cộng điểm vào `totalScore` của mỗi user
3. Status chuyển từ "Not Applied" → "Applied"
4. `appliedAt` được lưu

### Scenario 3: Trừ điểm từ một user
1. Click "Deduct" trên dòng assignee
2. Nhập "Amount to Deduct" (e.g., 2 points)
3. Nhập "Reason" (e.g., "Late submission")
4. Click "Deduct Points"
5. Điểm sẽ giảm, notes được update

### Scenario 4: Huỷ áp dụng điểm
1. Nếu score đã applied, click "Unapply"
2. Điểm sẽ bị trừ khỏi `totalScore` của user
3. Status quay về "Not Applied"

### Scenario 5: Hoàn thành task và cộng điểm
1. Click "Apply All Scores" để cộng điểm cho tất cả
2. Task tự động chuyển sang cột "Done"
3. Tất cả assignees nhận điểm

## Database Schema

```sql
CREATE TABLE task_scores (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    score INT NOT NULL DEFAULT 0,
    applied BOOLEAN NOT NULL DEFAULT false,
    scored_by BIGINT,
    scored_at TIMESTAMP,
    applied_at TIMESTAMP,
    notes VARCHAR(500),
    UNIQUE KEY unique_task_user (task_id, user_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (scored_by) REFERENCES users(id)
);
```

## Permission Check

Tất cả các endpoint yêu cầu `adminUserId` query parameter:
- Service sẽ validate user có role `ROLE_ADMIN` hoặc `ROLE_MANAGER`
- Nếu không, throw RuntimeException: "Only ADMIN or MANAGER can manage task scores"
- Frontend UI sẽ ẩn Manage Scores button nếu user không phải Admin/Manager

## Integration Notes

1. **TaskResponse DTO được update**: 
   - Mỗi assignee bây giờ có `score`, `applied`, `appliedAt`
   - TaskService inject TaskScoreRepository để lấy score khi mapping

2. **User Model không thay đổi**:
   - `totalScore` field đã tồn tại
   - Service sẽ update nó khi apply/unapply scores

3. **Database Migration**:
   - Cần chạy DDL để tạo bảng `task_scores`
   - Spring JPA sẽ auto-create nếu `spring.jpa.hibernate.ddl-auto=update`

## Error Handling

- Nếu user không tồn tại: "User not found"
- Nếu task không tồn tại: "Task not found"
- Nếu không phải Admin/Manager: "Only ADMIN or MANAGER can manage task scores"
- Nếu score không tồn tại: "Score not found for task X and user Y"

API trả về HTTP 400 Bad Request với error message

## Testing

Có thể test các endpoint bằng Postman:

```
1. GET /api/task-scores/task/1 - Lấy tất cả score của task 1
2. POST /api/task-scores/set?adminUserId=1
   Body: {"taskId": 1, "userId": 2, "score": 10, "notes": "Good"}
3. PATCH /api/task-scores/1/2/deduct?deductAmount=2&reason=Late&adminUserId=1
4. POST /api/task-scores/1/apply?adminUserId=1
5. DELETE /api/task-scores/1/2?adminUserId=1
```
