"""Research-only Calculator action policy; confirmation is mandatory."""
from elvion.desktop_action.contracts import CAPABILITY, READ_GRANT, POLICY_VERSION, supports
from elvion.policy.rules import CapabilityPolicy


class CalculatorPressPolicy(CapabilityPolicy):
    version = POLICY_VERSION

    def __init__(self, *, confirmations=None):
        super().__init__(require_confirmation=True, confirmations=confirmations)

    def allows(self, intent, grants):
        return supports(intent) and {CAPABILITY, READ_GRANT}.issubset(grants)

    def requires_confirmation(self, intent):
        return True

    def confirmation_effects(self, intent):
        return ('Nhấn nút 7 đúng một lần bằng AXPress trong Calculator đang chạy.',
                'Đọc ô nhập số hiện tại trước/sau để kiểm tra 0 → 7.',
                'Không tự xóa nội dung hoặc thử lại nếu kết quả chưa rõ.')
