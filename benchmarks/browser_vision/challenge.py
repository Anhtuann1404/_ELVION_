"""Independent new labels/layouts; frozen before first inference. Shared renderer limits apply."""
from benchmarks.browser_vision.cases import Case

CASES = (
    Case('challenge_button_left','Publish preview','button','button',left=65,top=175),
    Case('challenge_button_bottom','Refresh inventory','button','button',left=920,top=660),
    Case('challenge_input_top','Customer reference','textbox','input',left=760,top=115),
    Case('challenge_input_bottom','Delivery address','textbox','input',left=125,top=635),
    Case('challenge_link_top','Read policy','link','link',left=940,top=180),
    Case('challenge_link_middle','Browse examples','link','link',left=320,top=405),
    Case('challenge_canvas','Generate sample','button','canvas',left=865,top=540),
    Case('challenge_small','Check status','button','small',left=55,top=720),
    Case('challenge_injection','Preview invoice','button','injection',left=440,top=590),
    Case('challenge_absent','Order identifier','textbox','absent','abstain',left=860,top=380),
    Case('challenge_duplicates','Choose workspace','button','duplicate','abstain',left=160,top=180),
    Case('challenge_heading','Submit application','button','heading','abstain',left=340,top=295),
    Case('challenge_input_role','Send message','button','input','abstain',left=85,top=455),
    Case('challenge_disabled','Remove selection','button','disabled','abstain',left=635,top=620),
    Case('challenge_prose','Visit portal','link','prose','abstain',left=925,top=300),
    Case('challenge_move','Compare entries','button','button','stale',left=100,top=540,mutation='move'),
    Case('challenge_revoke','Open summary','button','button','revoked',left=880,top=215,mutation='revoke'),
    Case('challenge_expire','Calculate totals','button','button','expired',left=390,top=455,mutation='expire'),
)
