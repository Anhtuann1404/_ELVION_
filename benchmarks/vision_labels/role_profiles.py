"""Explicit research-only prompt profiles, shared by native and cached runners."""

ROLE_EVIDENCE_NOTE = (
    ' First locate the supplied candidate bounding box in the attached image. '
    'Coordinates refer to this attached image, not a previous image. '
    'Determine role from visible styling and surrounding layout, never from label wording. '
    'Unadorned dark headings and prose are text even when their words describe navigation. '
    'Do not invent an underline or navigation context. Links need visible navigation evidence, '
    'such as link styling with an underline or a clear navigation grouping. '
    'A colon or other punctuation does not change element type. '
    'If visual evidence does not distinguish a link from ordinary text, return unknown.'
)

PROFILES = ('current', 'visual-evidence-v1')


def with_role_profile(complete, profile):
    if profile not in PROFILES:
        raise ValueError('INVALID_ROLE_PROFILE')

    def wrapped(**kwargs):
        if profile == 'visual-evidence-v1' and kwargs['role'] in (
                'actual_element_type', 'classify_actual_type'):
            kwargs['system'] += ROLE_EVIDENCE_NOTE
        return complete(**kwargs)

    return wrapped
