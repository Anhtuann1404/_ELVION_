# Đặc tả thiết kế giao diện ELVION (UI Design Specification)

Phiên bản: 0.1 — Chốt ngày 29/10/2026.  
Tài liệu này chuẩn hóa toàn bộ ngôn ngữ thiết kế, bố cục, bảng màu và hành vi tương tác của giao diện người dùng ELVION trên macOS (MacBook Pro M5).

---

## 1. Triết lý thiết kế

> **"Tàng hình khi nhàn rỗi — Xuất hiện tức thì — Minh bạch tuyệt đối khi hành động"**

* **Phong cách chủ đạo:** **Apple Liquid Glass (Kính lỏng)** — ứng dụng chiều sâu khúc xạ ánh sáng đa tầng (`backdrop-filter: blur`), viền gương phản chiếu (`specular highlight`) tiệp màu tự nhiên vào hình nền dark mode của macOS.
* **Tối giản (Minimalist):** Không tạo cửa sổ ứng dụng hình chữ nhật cồng kềnh; chỉ xuất hiện dạng viên nang nổi (Floating Capsule) lơ lửng giữa màn hình khi kích hoạt bằng phím tắt `Option + Space` hoặc Push-to-Talk.
* **Bảng màu chủ đạo:** **Pure Titanium / Starlight Silver** — đơn sắc ánh kim cao cấp, đồng bộ hoàn hảo với thân máy nhôm Space Black / Silver của MacBook Pro M5.

---

## 2. Cấu trúc bố cục (Layout Structure)

Viên nang ELVION gồm 2 tầng chính và 1 thẻ trượt ngữ cảnh (Contextual Drawer):

```
┌────────────────────────────────────────────────────────┐
│  ELVION Dynamic Capsule [Pure Titanium Liquid Glass]    │
│                                                        │
│  [1] TẦNG TRÊN: Sóng âm kim loại lỏng (Mercury Wave)   │
│      ~~~~~~~~~~~~/\/\/\/\/\/\/\~~~~~~~~~~~~            │
│      (Phản hồi thời gian thực theo giọng nói/suy luận) │
│                                                        │
│  ─────────────────── Hairline Divider ──────────────── │
│                                                        │
│  [2] TẦNG DƯỚI: Thanh Text bo tròn (Rounded Pill Bar)  │
│      (🎙️) [ Nhập lệnh hoặc nói với ELVION... ] [⚡AIMS] (↵)│
└────────────────────────────────────────────────────────┘
                           │
                           ▼ (Trượt xuống khi có sự kiện)
┌────────────────────────────────────────────────────────┐
│  [3] THẺ PHỤ NGỮ CẢNH (Confirmation / Verifier Toast) │
│      🔒 #d9f3a71b • Apple Notes                        │
│      Xem trước: Tạo ghi chú "Ôn tập AI"                │
│      [Từ chối (Esc)]             [Phê duyệt (↵)]       │
└────────────────────────────────────────────────────────┘
```

### Chi tiết các tầng:
1. **Tầng trên — Dải sóng âm (Fluid Waveform):**
   * Biểu diễn dạng đường cong sóng mềm mại (Bezier fluid curves) phát sáng trắng bạc và xám kim loại lỏng.
   * Biên độ sóng tự động co giãn theo âm lượng micro (Push-to-Talk) hoặc chuyển sang nhịp thở êm (breathing shimmer) khi planner đang xử lý.
2. **Tầng dưới — Thanh Text tròn (Pill-shaped Input Bar):**
   * Bo cong tuyệt đối (`rounded-full`), nền kính tối mờ (`rgba(24, 24, 27, 0.7)`).
   * **Bên trái:** Icon Micro cho phép nhấp chuột để chuyển đổi Push-to-Talk.
   * **Chính giữa:** Trường nhập liệu văn bản với typography SF Pro chuẩn macOS.
   * **Huy hiệu AIMS:** Nhỏ gọn, hiển thị phương thức hiện thời (`⚡ Native API`, `♿ Accessibility`, `👁️ Vision UI`).
   * **Bên phải:** Nút mũi tên Return màu trắng bạc ánh kim để gửi lệnh nhanh.
3. **Thẻ phụ trượt (Contextual Popover):**
   * Tự động trượt êm ái ra từ cạnh đáy viên nang khi:
     * **Yêu cầu xác nhận (Confirmation Request):** Hiển thị rõ ứng dụng đích, preview nội dung và mã digest an toàn `#d9f3a...`.
     * **Kết quả Verifier (Evidence Toast):** Báo trạng thái kiểm chứng hoàn tất (ví dụ: `Đã kiểm chứng • 12ms`), tự động thu lại sau 3.5 giây.

---

## 3. Hệ thống Design Tokens (Pure Titanium)

### A. Màu sắc (Color Palette)
| Token | Giá trị CSS | Ý nghĩa sử dụng |
| :--- | :--- | :--- |
| `--glass-bg` | `linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.03))` | Nền kính lỏng trong suốt |
| `--glass-border` | `rgba(255, 255, 255, 0.35)` | Viền kính phản xạ ánh sáng |
| `--specular-top` | `inset 0 1px 1px rgba(255, 255, 255, 0.45)` | Ánh sáng phản chiếu gờ trên |
| `--ambient-glow` | `rgba(255, 255, 255, 0.12)` | Quầng sáng trắng mờ phía sau |
| `--pill-bg` | `rgba(24, 24, 27, 0.65)` | Nền thanh text tròn (Deep Titanium) |
| `--wave-primary` | `#ffffff` $\rightarrow$ `#e4e4e7` | Sóng âm chính (Starlight White) |
| `--wave-secondary` | `#a1a1aa` $\rightarrow$ `#d4d4d8` | Sóng âm thứ cấp (Metallic Silver) |
| `--accent-success` | `#34d399` | Xanh ngọc điểm xuyết cho Verifier Verified |
| `--accent-warning` | `#fbbf24` | Vàng hổ phách cho Action Confirmation Digest |
| `--accent-danger` | `#f43f5e` | Đỏ hồng khi từ chối quyền hoặc lỗi |

### B. Hiệu ứng kính (Glassmorphism & Vibrancy)
* **Backdrop Blur:** `blur(28px) saturate(180%)` (tương đương `NSVisualEffectView.Material.hudWindow` trong macOS AppKit).
* **Bóng đổ (Shadow):** `0 20px 45px rgba(0, 0, 0, 0.55)`.
* **Độ bo góc:**
  * Thân viên nang: `rounded-[28px]` (chuẩn squircle của Apple).
  * Thanh nhập liệu: `rounded-full` (dạng viên thuốc đối xứng).
  * Thẻ phụ ngữ cảnh: `rounded-2xl`.

### C. Kích thước (Dimensions)
* **Chiều rộng chuẩn:** `440px` (tối đa `480px` trên màn hình Retina MacBook M5).
* **Chiều cao nhàn rỗi:** `~170px`.
* **Chiều cao khi bung thẻ xác nhận:** `~290px`.

---

## 4. Hành vi tương tác (Interaction Flow)

1. **Kích hoạt (Invoke):**
   * Người dùng nhấn `Option + Space` $\rightarrow$ Viên nang xuất hiện tại vị trí 1/3 phía trên màn hình với hiệu ứng bung mờ (scale from 0.95 + fade in 150ms).
2. **Nhập lệnh (Voice / Text):**
   * Nếu giữ phím Push-to-Talk hoặc bấm icon Mic: Dải sóng âm bung nở mạnh theo giọng nói, chấm trạng thái nháy đỏ hồng.
   * Nếu gõ văn bản: Người dùng nhập trực tiếp vào thanh text pill, sóng âm chuyển sang nhịp thở êm dịu màu bạc Starlight.
3. **Phân rã & Chọn đường AIMS:**
   * Sau khi nhận lệnh, huy hiệu AIMS nhấp nháy cập nhật phương thức tối ưu được chọn (`⚡ Native API`, `♿ Accessibility`, `👁️ Vision UI`).
4. **Xác nhận hành động an toàn (Confirmation):**
   * Nếu policy yêu cầu xác nhận (hành động nhạy cảm): Thẻ xác nhận trượt xuống hiển thị mã digest. Người dùng chỉ cần nhấn `Enter` để phê duyệt hoặc `Esc` để hủy.
5. **Kiểm chứng & Ẩn (Verification & Dismiss):**
   * Verifier xác nhận hậu điều kiện $\rightarrow$ Huy hiệu xanh báo `Đã kiểm chứng` $\rightarrow$ Viên nang tự động thu gọn và biến mất.

---

## 5. Lộ trình triển khai công nghệ

* **Sprint 0:** Tiếp tục dùng CLI văn bản để hoàn thiện lõi logic, schema và verifier.
* **Sprint tiếp theo (GUI Implementation):**
  * Xây dựng module native trong `native/macos/` bằng **SwiftUI + AppKit**.
  * Dùng `NSPanel` dạng non-activating floating HUD với nền trong suốt `NSVisualEffectView`.
  * Kết nối 2 chiều với Python Core qua **Unix Domain Socket** (`/tmp/elvion.sock`).
