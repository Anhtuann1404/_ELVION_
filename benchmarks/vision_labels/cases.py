"""Fixed, hand-labelled punctuation and near-match cases, authored before inference."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from html import escape
import json

WIDTH, HEIGHT = 1280, 800


@dataclass(frozen=True)
class Element:
    id: str
    role: str  # button | textbox | link | heading | prose
    label: str
    x: int
    y: int
    width: int
    height: int
    disabled: bool = False


@dataclass(frozen=True)
class Case:
    id: str
    split: str
    group: str
    target: str
    role: str
    expected: str  # found | not_found | ambiguous
    rationale: str
    elements: tuple[Element, ...]
    truth_ids: tuple[str, ...] = ()


def e(id, role, label, x, y, w=190, h=54, disabled=False):
    return Element(id, role, label, x, y, w, h, disabled)


CASES = (
    # Development split: one exact control, each punctuation form, then independent safety cases.
    Case('vl_d01_plain_button', 'dev', 'plain', 'Save workspace', 'button', 'found',
         'Unpunctuated enabled button is one exact target.', (e('a','button','Save workspace',215,158),), ('a',)),
    Case('vl_d02_period_button', 'dev', 'terminal_period', 'Send memo.', 'button', 'found',
         'The period is printed and belongs to the button label.', (e('a','button','Send memo.',850,132,220,58),), ('a',)),
    Case('vl_d03_comma_link', 'dev', 'terminal_comma', 'Overview,', 'link', 'found',
         'The comma is printed at the end of the link.', (e('a','link','Overview,',80,480,170,40),), ('a',)),
    Case('vl_d04_colon_textbox', 'dev', 'terminal_colon', 'Project:', 'textbox', 'found',
         'The placeholder ends in a visible colon.', (e('a','textbox','Project:',475,295,310,52),), ('a',)),
    Case('vl_d05_semicolon_button', 'dev', 'terminal_semicolon', 'Review;', 'button', 'found',
         'The semicolon is part of the button text.', (e('a','button','Review;',1000,608,170,50),), ('a',)),
    Case('vl_d06_exclamation_link', 'dev', 'terminal_exclamation', 'Proceed!', 'link', 'found',
         'The exclamation mark is printed in the link.', (e('a','link','Proceed!',520,570,175,42),), ('a',)),
    Case('vl_d07_question_button', 'dev', 'terminal_question', 'Continue?', 'button', 'found',
         'The question mark is part of the enabled button.', (e('a','button','Continue?',45,230,215,56),), ('a',)),
    Case('vl_d08_internal_punctuation', 'dev', 'internal_punctuation', 'Sort: newest', 'textbox', 'found',
         'Internal colon and exact spelling both matter.', (e('a','textbox','Sort: newest',730,340,300,50),), ('a',)),
    Case('vl_d09_multiple_terminal', 'dev', 'multiple_terminal', 'Really?!', 'button', 'found',
         'Both final marks are visible; neither is discarded.', (e('a','button','Really?!',290,640,165,52),), ('a',)),
    Case('vl_d10_vietnamese', 'dev', 'vietnamese', 'Tạo báo cáo.', 'button', 'found',
         'Vietnamese accents and final period are exact.', (e('a','button','Tạo báo cáo.',770,214,225,54),), ('a',)),
    Case('vl_d11_missing_period', 'dev', 'near_only_punct', 'Publish', 'button', 'not_found',
         'Only Publish. exists; removing its real period is not an exact match.',
         (e('near','button','Publish.',180,365,190,54),)),
    Case('vl_d12_changed_word', 'dev', 'near_word', 'Save file', 'button', 'not_found',
         'Save files differs by a meaningful final letter.', (e('near','button','Save files',725,510,205,54),)),
    Case('vl_d13_duplicate_button', 'dev', 'duplicate', 'Inspect record', 'button', 'ambiguous',
         'Two enabled buttons have identical labels and roles.',
         (e('a','button','Inspect record',75,185,235,56), e('b','button','Inspect record',935,620,235,56)), ('a','b')),
    Case('vl_d14_wrong_role_text', 'dev', 'wrong_role_text', 'Open guide', 'link', 'not_found',
         'The same words occur only in a heading and prose, neither a link.',
         (e('heading','heading','Open guide',180,170,270,48), e('prose','prose','Open guide',825,555,235,40))),
    Case('vl_d15_absent', 'dev', 'absent', 'Create invoice', 'button', 'not_found',
         'The requested label is absent despite a related button.', (e('near','button','Review invoice',650,208,220,54),)),

    # Held-out: different labels/layouts; never relabel after seeing model outputs.
    Case('vl_h01_plain_link', 'held_out', 'plain', 'Audit trail', 'link', 'found',
         'One exact unpunctuated link.', (e('a','link','Audit trail',980,115,190,40),), ('a',)),
    Case('vl_h02_period_link', 'held_out', 'terminal_period', 'Terms apply.', 'link', 'found',
         'The link really ends with a period.', (e('a','link','Terms apply.',190,535,205,43),), ('a',)),
    Case('vl_h03_comma_button', 'held_out', 'terminal_comma', 'Queue item,', 'button', 'found',
         'Visible comma is part of the button.', (e('a','button','Queue item,',850,410,205,55),), ('a',)),
    Case('vl_h04_colon_link', 'held_out', 'terminal_colon', 'Methods:', 'link', 'found',
         'The displayed link ends in a colon.', (e('a','link','Methods:',300,180,160,42),), ('a',)),
    Case('vl_h05_semicolon_textbox', 'held_out', 'terminal_semicolon', 'Tag;', 'textbox', 'found',
         'The textbox placeholder includes a semicolon.', (e('a','textbox','Tag;',55,615,285,50),), ('a',)),
    Case('vl_h06_exclamation_button', 'held_out', 'terminal_exclamation', 'Confirm now!', 'button', 'found',
         'The exclamation mark is printed on the button.', (e('a','button','Confirm now!',610,130,245,57),), ('a',)),
    Case('vl_h07_question_link', 'held_out', 'terminal_question', 'How it works?', 'link', 'found',
         'The question mark is visible in the link.', (e('a','link','How it works?',745,620,235,42),), ('a',)),
    Case('vl_h08_internal_punctuation', 'held_out', 'internal_punctuation', 'Status: ready', 'link', 'found',
         'An internal colon distinguishes the link wording.', (e('a','link','Status: ready',140,270,245,42),), ('a',)),
    Case('vl_h09_multiple_terminal', 'held_out', 'multiple_terminal', 'Wait...!', 'button', 'found',
         'Ellipsis plus exclamation mark are visible.', (e('a','button','Wait...!',965,520,180,55),), ('a',)),
    Case('vl_h10_vietnamese', 'held_out', 'vietnamese', 'Xem chi tiết?', 'link', 'found',
         'Accented Vietnamese and final question mark are exact.', (e('a','link','Xem chi tiết?',495,440,230,42),), ('a',)),
    Case('vl_h11_plain_and_period', 'held_out', 'near_distractor', 'Publish', 'button', 'found',
         'Publish is unique; Publish. is a separate near-matching distractor.',
         (e('a','button','Publish',95,155,180,54), e('near','button','Publish.',925,590,180,54)), ('a',)),
    Case('vl_h12_period_and_plain', 'held_out', 'near_distractor', 'Archive.', 'button', 'found',
         'Archive. is unique; Archive without its period is a separate distractor.',
         (e('near','button','Archive',190,565,180,54), e('a','button','Archive.',870,245,180,54)), ('a',)),
    Case('vl_h13_duplicate_link', 'held_out', 'duplicate', 'Open ledger', 'link', 'ambiguous',
         'Identical enabled links appear far apart.',
         (e('a','link','Open ledger',70,220,205,42), e('b','link','Open ledger',950,640,205,42)), ('a','b')),
    Case('vl_h14_disabled', 'held_out', 'disabled', 'Remove item', 'button', 'not_found',
         'The exact button is disabled, so no actionable target exists.',
         (e('disabled','button','Remove item',660,360,210,56,True),)),
    Case('vl_h15_textbox_wrong_role', 'held_out', 'wrong_role', 'Search catalog', 'button', 'not_found',
         'The exact words are in a textbox, not a button.',
         (e('textbox','textbox','Search catalog',300,390,300,52),)),
)


def render(case: Case) -> str:
    controls = []
    for element in case.elements:
        label = escape(element.label, quote=True)
        common = (f'data-fixture-id="{element.id}" style="left:{element.x}px;top:{element.y}px;'
                  f'width:{element.width}px;height:{element.height}px"')
        if element.role == 'button':
            controls.append(f'<button {common}{" disabled" if element.disabled else ""}>{label}</button>')
        elif element.role == 'textbox':
            controls.append(f'<input {common} aria-label="{label}" placeholder="{label}">')
        elif element.role == 'link':
            controls.append(f'<a {common} href="#fixture">{label}</a>')
        elif element.role == 'heading':
            controls.append(f'<h2 {common}>{label}</h2>')
        elif element.role == 'prose':
            controls.append(f'<p {common}>{label}</p>')
        else:
            raise ValueError('Invalid element role')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Label fixture</title>
<style>body{{margin:0;width:{WIDTH}px;height:{HEIGHT}px;background:#f5f8fb;font:18px Arial;color:#15334c}}
header{{height:68px;background:#173954;color:#fff;padding:20px 34px;box-sizing:border-box}}
button,input,a,h2,p{{position:absolute;box-sizing:border-box;margin:0}}
button{{background:#286fa8;color:#fff;border:2px solid #155184;border-radius:7px;font:20px Arial}}
button:disabled{{background:#e3e6ea;color:#a3a8ae;border-color:#c8cdd2}}
input{{background:#fff;border:2px solid #8ba1b2;border-radius:5px;padding:11px;font:18px Arial}}
a{{color:#145ba9;text-decoration:underline;padding:7px;font:19px Arial}}
h2{{font:28px Arial}}p{{font:19px Arial}}</style>
<body><header>Knowledge workspace</header>{''.join(controls)}</body></html>'''


def manifest_sha256(cases=CASES) -> str:
    payload = [{'case': asdict(case), 'html': render(case)} for case in cases]
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def check_cases(cases=CASES):
    if len(cases) < 24 or len({case.id for case in cases}) != len(cases):
        raise ValueError('Invalid case count or duplicate ID')
    splits = {name: sum(case.split == name for case in cases) for name in ('dev','held_out')}
    if min(splits.values()) < 12 or abs(splits['dev'] - splits['held_out']) > 1:
        raise ValueError('Unbalanced split')
    for case in cases:
        if (case.split not in splits or case.role not in {'button','textbox','link'} or
                case.expected not in {'found','not_found','ambiguous'} or not case.rationale or
                not case.target or not case.elements or len({e.id for e in case.elements}) != len(case.elements)):
            raise ValueError('Invalid case metadata')
        matches = tuple(e.id for e in case.elements if e.role == case.role and not e.disabled and e.label == case.target)
        if matches != case.truth_ids or case.expected != ('found' if len(matches)==1 else 'ambiguous' if matches else 'not_found'):
            raise ValueError('Expected outcome does not match authored controls')
        for element in case.elements:
            if (element.role not in {'button','textbox','link','heading','prose'} or
                    min(element.x,element.y) < 0 or min(element.width,element.height) <= 0 or
                    element.x + element.width > WIDTH or element.y + element.height > HEIGHT):
                raise ValueError('Invalid control bounds')
        html = render(case)
        if '<script' in html or 'http://' in html or 'https://' in html:
            raise ValueError('External or executable fixture resource')
    return cases
