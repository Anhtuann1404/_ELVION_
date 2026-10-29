# ELVION

> **ELVION** — Trợ lý cá nhân điều khiển macOS bằng giọng nói và chữ, ưu tiên xử lý trên máy (local-first) cho MacBook Pro M5.

---

## Giới thiệu

ELVION là dự án dài hạn hướng tới xây dựng một trợ lý cá nhân thông minh, an toàn, với khả năng tự động lựa chọn giao diện điều khiển (AIMS - Adaptive Interface Method Selection) giữa Native/API, Accessibility/DOM và Vision UI.

Hệ thống được thiết kế theo nguyên tắc:
- **Local-first**: Ưu tiên xử lý dữ liệu và suy luận trực tiếp trên thiết bị; cloud model chỉ được gọi khi có sự cho phép cụ thể theo từng tác vụ.
- **Bảo mật & Quyền riêng tư**: Chính sách quyền nghiêm ngặt, cơ chế xác nhận hai lớp (confirmation digest) cho các thao tác có tác động bên ngoài (gửi tin, sửa/xóa dữ liệu).
- **Kiểm chứng độc lập**: Verifier đánh giá kết quả thực thi dựa trên bằng chứng và hậu điều kiện (postcondition).

---

## Tài liệu chi tiết

Toàn bộ tài liệu thiết kế và đặc tả kiến trúc được đặt trong thư mục [`Docs/`](Docs/):

1. [**Docs/PROJECT_PLAN.md**](Docs/PROJECT_PLAN.md): Tầm nhìn, nguyên tắc sản phẩm, các mốc phát triển và tiêu chí đánh giá.
2. [**Docs/ARCHITECTURE.md**](Docs/ARCHITECTURE.md): Kiến trúc module, luồng thực thi và cơ chế AIMS.
3. [**Docs/API_CONTRACTS.md**](Docs/API_CONTRACTS.md): Đặc tả hợp đồng dữ liệu nội bộ, adapter, quyền và mã lỗi chuẩn.
4. [**Docs/TECH_STACK.md**](Docs/TECH_STACK.md): Lựa chọn công nghệ (Python core, Swift helper, SQLite, Keychain) và nguyên tắc thay thế.
5. [**Docs/CURRENT_TASKS.md**](Docs/CURRENT_TASKS.md): Kế hoạch Sprint 0 (Bộ xương chạy được), backlog và tiêu chí nghiệm thu.
6. [**Docs/DECISIONS.md**](Docs/DECISIONS.md): Nhật ký các quyết định kiến trúc đã thống nhất và điểm còn mở.
