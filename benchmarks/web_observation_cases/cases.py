"""Candidate targets for independent screenshot annotation; no inferred oracle."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from ipaddress import ip_address
import json
import re
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Case:
    id: str
    split: str
    url: str
    target: str
    role: str
    language: str
    group: str
    rationale: str
    capture_status: str
    expected_status: str
    expected_basis: str


_PY = 'https://docs.python.org/3/tutorial/index.html'
_MDN = 'https://developer.mozilla.org/en-US/docs/Web/HTML'
_WIKI = 'https://vi.wikipedia.org/wiki/Trang_Ch%C3%ADnh'
_GH = 'https://docs.github.com/en'
_W3C = 'https://www.w3.org/TR/WCAG22/'
_CHROME = 'https://developer.chrome.com/docs/devtools/'


def _candidate(id: str, split: str, url: str, target: str, role: str,
               language: str, group: str, rationale: str) -> Case:
    return Case(id, split, url, target, role, language, group, rationale,
                'provisional', 'undetermined',
                'URL/page text checked 2026-10-30; viewport screenshot and independent annotation pending.')


CASES = (
    _candidate('wo_d01_python_search', 'dev', _PY, 'Search', 'textbox', 'en', 'visible_candidate',
               'Search input candidate; confirm rendered label and visibility.'),
    _candidate('wo_d02_python_modules', 'dev', _PY, 'Installing Python Modules', 'link', 'en', 'long_label',
               'Tutorial contents candidate; test whether the link is within the viewport.'),
    _candidate('wo_d03_python_offscreen', 'dev', _PY, 'What Now?', 'link', 'en', 'off_viewport',
               'Contents link may fall below the initial viewport; annotate only image pixels.'),
    _candidate('wo_d04_python_absent', 'dev', _PY, 'Create invoice', 'button', 'en', 'absent_candidate',
               'Deliberately unrelated target; verify absence in screenshot before scoring.'),
    _candidate('wo_d05_mdn_elements', 'dev', _MDN, 'Elements', 'link', 'en', 'short_label',
               'Short navigation link amid many nearby links.'),
    _candidate('wo_d06_mdn_html_reference', 'dev', _MDN, 'HTML reference', 'link', 'en', 'long_label',
               'Navigation link candidate; compare with heading text and viewport.'),
    _candidate('wo_d07_mdn_punctuation', 'dev', _MDN, 'HTML reference.', 'link', 'en', 'near_punctuation',
               'Period variant of a page label; only screenshot determines exact match.'),
    _candidate('wo_d08_mdn_wrong_role', 'dev', _MDN, 'HTML: HyperText Markup Language', 'button', 'en', 'wrong_role',
               'Page title or link-like text must not be assumed to be a button.'),
    _candidate('wo_d09_wiki_search_input', 'dev', _WIKI, 'Tìm kiếm trên Wikipedia', 'textbox', 'vi', 'vietnamese',
               'Vietnamese search field candidate; require rendered evidence.'),
    _candidate('wo_d10_wiki_search_button', 'dev', _WIKI, 'Tìm kiếm', 'button', 'vi', 'vietnamese',
               'Search button candidate; nearby search link may have same words but different role.'),
    _candidate('wo_d11_wiki_guide', 'dev', _WIKI, 'Hướng dẫn', 'link', 'vi', 'short_label',
               'Short accented navigation link candidate.'),
    _candidate('wo_d12_wiki_duplicate', 'dev', _WIKI, 'Trang Chính', 'link', 'vi', 'duplicate_candidate',
               'Source lists repeated links; annotate ambiguous only if two same-role links are visible.'),
    _candidate('wo_h01_github_start', 'held_out', _GH, 'Get started', 'link', 'en', 'short_label',
               'Docs category link candidate among other categories.'),
    _candidate('wo_h02_github_migrations', 'held_out', _GH, 'Migrations', 'link', 'en', 'short_label',
               'Adjacent navigation link candidate.'),
    _candidate('wo_h03_github_search', 'held_out', _GH, 'Search for anything...', 'textbox', 'en', 'punctuation',
               'Search UI text with ellipsis; verify whether it belongs to a visible textbox.'),
    _candidate('wo_h04_github_wrong_role', 'held_out', _GH, 'GitHub Docs', 'button', 'en', 'wrong_role',
               'Brand/title text is not sufficient button evidence.'),
    _candidate('wo_h05_w3c_recommendation', 'held_out', _W3C, 'W3C Recommendation', 'link', 'en', 'short_label',
               'Document metadata link candidate.'),
    _candidate('wo_h06_w3c_latest', 'held_out', _W3C, 'Latest published version:', 'link', 'en', 'wrong_role',
               'Metadata label may be plain text beside a URL link; do not infer role.'),
    _candidate('wo_h07_w3c_errata', 'held_out', _W3C, 'Errata exists', 'link', 'en', 'off_viewport',
               'Document metadata link candidate; viewport position needs capture.'),
    _candidate('wo_h08_w3c_absent', 'held_out', _W3C, 'Pay invoice', 'button', 'en', 'absent_candidate',
               'Deliberately unrelated control; screenshot must establish absence.'),
    _candidate('wo_h09_chrome_docs', 'held_out', _CHROME, 'Docs', 'link', 'en', 'short_label',
               'Top navigation link candidate.'),
    _candidate('wo_h10_chrome_get_started', 'held_out', _CHROME, 'Get started', 'link', 'en', 'duplicate_candidate',
               'Source lists this wording in navigation and content; count visible same-role matches.'),
    _candidate('wo_h11_chrome_filter', 'held_out', _CHROME, 'Filter', 'textbox', 'en', 'visible_candidate',
               'Sidebar filter field candidate; verify visible role and label.'),
    _candidate('wo_h12_chrome_icon', 'held_out', _CHROME, 'Search', 'button', 'en', 'unlabeled_icon',
               'Source lists blank buttons; an icon without visible label must remain uncertain.'),
)


def _domain(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname
    if (parts.scheme != 'https' or not host or parts.username is not None or
            parts.password is not None or parts.port not in (None, 443) or
            parts.fragment or not parts.path.startswith('/')):
        raise ValueError(f'Invalid public HTTPS URL: {url!r}')
    host = host.lower().rstrip('.')
    if (host in {'localhost'} or host.endswith(('.localhost', '.local', '.internal',
                                                '.test', '.invalid', '.example'))):
        raise ValueError(f'Local or reserved host: {url!r}')
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError(f'Literal IP URL is not allowed: {url!r}')
    labels = host.split('.')
    if len(labels) < 2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                              for label in labels):
        raise ValueError(f'Invalid DNS host: {url!r}')
    # This manifest uses only simple .org/.com domains, not public-suffix parsing.
    return '.'.join(labels[-2:])


def check_cases(cases=CASES):
    cases = tuple(cases)
    if len(cases) < 24 or len({case.id for case in cases}) != len(cases):
        raise ValueError('Expected at least 24 unique cases')
    domains = {'dev': set(), 'held_out': set()}
    for case in cases:
        if (not re.fullmatch(r'wo_[a-z0-9_]+', case.id) or
                case.split not in domains or case.role not in {'button', 'textbox', 'link'} or
                case.capture_status not in {'provisional', 'confirmed'} or
                case.expected_status not in {'found', 'not_found', 'ambiguous', 'undetermined'} or
                not all(isinstance(x, str) and x.strip() for x in
                        (case.target, case.language, case.group, case.rationale, case.expected_basis))):
            raise ValueError(f'Invalid case metadata: {getattr(case, "id", None)}')
        if case.capture_status == 'provisional' and case.expected_status != 'undetermined':
            raise ValueError(f'Provisional case has asserted oracle: {case.id}')
        if case.capture_status == 'confirmed' and case.expected_status == 'undetermined':
            raise ValueError(f'Confirmed case lacks oracle: {case.id}')
        domains[case.split].add(_domain(case.url))
    if sum(case.split == 'dev' for case in cases) < 12 or sum(case.split == 'held_out' for case in cases) < 12:
        raise ValueError('Each split needs at least 12 cases')
    if domains['dev'] & domains['held_out']:
        raise ValueError('Development and held-out domains overlap')
    return cases


def manifest_sha256(cases=CASES) -> str:
    payload = [asdict(case) for case in cases]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256(encoded).hexdigest()
