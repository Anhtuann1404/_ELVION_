# Đối chiếu bbox Calculator với cửa sổ và màn hình — chỉ đọc

Lệnh desktop, sau khi mở Calculator bằng tay:

```bash
PYTHONPATH=src python3 scripts/check_desktop_geometry.py --label '7' --include-labels
```

Không click, di chuyển chuột, đổi focus, chụp màn hình hay ghi snapshot thô.
Cờ include-labels là opt-in để tìm nhãn qua AX; stdout không dump nhãn khác
hoặc tiêu đề cửa sổ. Chỉ in mã trạng thái và hình học mục tiêu/cửa sổ/màn hình.

## Kiểm tra gì

Helper `native/macos/DisplayGeometry.swift` đọc NSScreen và CGDisplayBounds.
AXPosition trong SDK AXAttributeConstants.h định nghĩa gốc tại góc trên trái
màn hình menu bar, trục y tăng xuống, đơn vị points; AXSize cũng dùng points.
Helper đổi frame AppKit sang hệ gốc đó và kiểm tra nó khớp CGDisplayBounds
trên từng displayID (sai lệch tối đa0,5point). Không khớp thì báo unavailable,
không tự nhân/chia tọa độ với backing scale.

Python validate protocol/giới hạn/type, đọc layout trước và sau snapshot AX.
Nếu hai mẫu layout khác thì từ chối. Build helper trước thu snapshot để không
làm snapshot hết hạn trong lúc compile. Locator giữ scope calculator_content.

`check_geometry` kiểm tra result/snapshot/node gắn đúng nhau, snapshot không
stale/future/truncated, target enabled có bbox khớp node, nằm hoàn toàn trong
AXWindow ancestor gần nhất và đúng một display. Negative x/y được giữ nguyên:
màn hình bên trái/phía trên màn hình chính có thể có origin âm. Target qua
ranh giới màn hình hoặc nhiều display trùng bounds không được gán đại.

## Đọc kết quả

- `geometry_consistent`: bbox nhất quán với cửa sổ AX và đúng một màn hình
  ở hai mẫu layout này. Đây chưa phải xác nhận vị trí pixel hoặc visibility.
- `DISPLAY_LAYOUT_CHANGED`, `DISPLAY_COORDINATE_MISMATCH`, thiếu windowbbox,
  snapshot stale hay target ngoài display: giữ unavailable và lý do cố định.
- `target_status`/`target_reason` cho biết bước tìm target đã thành công chưa.
- `display_scale` chỉ là metadata; bbox vẫn native AX screen points.

`actions=0`, `visibility_verified=false`, `freshness_for_execution=false`.
Hai mẫu layout khớp không loại trừ việc layout đã đổi rồi quay lại ở giữa.
Snapshot AX ghi timestamp cuối thu thập, từng node không được đọc atomic.
Chưa kiểm tra cửa sổ bị che/ẩn, target nằm ngoài vùng nhìn thấy của container,
focus hay stale giữa kiểm tra và hành động. Không chuyển bbox sang lệnh click,
không cấp authority token và chưa nối vào executor/AIMS.

## Kiểm thử

`tests/test_desktop_geometry.py` dùng fixtures xác định cho origin âm, scale,
window/display containment, binding node, stale/future/truncated, layout đổi,
protocol/duplicate keys, opt-in và một lần đọc AX. Fake tests không chứng
minh layout/AX thực tế trên desktop. Native helper compile/read được ghi
riêng trong BUG_LOG; cần người dùng gửi summary từ lệnh trên để chốt mốc thật.

## Native desktop do người dùng xác nhận —31/10/2026

Lệnh trả geometry_consistent/AX_WINDOW_AND_DISPLAY_CONTAIN_TARGET.
Target7 cóbbox[1103,-519,48,48],window[1093,-706,230,408],
display[62,-900,1600,900],scale1; containment đúng. Hai mẫu layoutkhớp,
age35,631625ms. Đã xác minh originâm phù hợp layoutở lượt này.
Summary từdesktop người dùng,không phải screenshot/pixel verification.
actions0,visibility_verifiedfalse,freshness_for_executionfalse giữ nguyên;
chưa có thao tác hoặc kết luận targetkhôngbịche/đủfreshchoexecution.
