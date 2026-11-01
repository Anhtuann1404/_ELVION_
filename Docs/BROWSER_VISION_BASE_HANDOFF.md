# Nền browser/Vision độc lập

Ngày 01/11/2026. Nhánh `feat/browser-vision-base` tách mã browser, Vision,
benchmark và kiểm thử từ working tree chung sang cây sạch dựa trên `origin/main`.
Không sao chép hoặc sửa các file Apple Music đang làm dở.

## Phạm vi

- Gồm `src/elvion/browser/`, `src/elvion/vision/`, adapter/planner/policy/verifier
  web, `models/structured.py`, trace allowlist web, benchmark và test tương ứng.
- Chưa chứa tích hợp CLI/GUI/voice ở `interface/session.py` và các file dùng
  chung khác. Một test CLI trong `test_browser_workflow.py` được skip rõ lý do;
  không tính nó là đã đạt. YouTube có thể dùng API thư viện từ nhánh này rồi
  bàn giao điểm tích hợp CLI riêng.
- Không gồm web summary/citation đang phát triển đồng thời trên nhánh chính.
  Tài liệu `WEB_BASELINE.md` là báo cáo lịch sử working tree gốc, không phải
  xác nhận rằng mọi luồng CLI của nhánh này đã được đóng gói.
- Không có phép đo native mới trong worktree. Báo cáo Vision trước đây giữ
  nguyên phạm vi fixture/public web và quyết định chưa bật live Vision.

## Kiểm chứng

`PYTHONPATH=src:. python3 -m unittest discover -s tests -q`:
320 tests đạt, 1 skip (CLI integration). Đây là fake/unit/regression, không
thay thế model thật. Chromium fixture DOM đã chạy bằng interpreter
`/Users/yingjunn_/Study_/ELVION/.venv-browser/bin/python` với
`PYTHONPATH=src:. python scripts/check_browser.py --mode dom`: PASS, click
thật và đọc lại `data-done` độc lập, PNG 1280×800. Chưa có phép đo Vision
native mới trên nhánh này.

## Tích hợp

Nhánh YouTube lấy nền từ commit này bằng rebase hoặc merge. Nhánh chính tiếp
tục sở hữu `interface/session.py`, quyền phiên và tài liệu công việc chung;
đối chiếu riêng các hunk web trước khi tích hợp, không ghi đè working tree.
