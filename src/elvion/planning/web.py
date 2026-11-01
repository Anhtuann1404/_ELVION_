import re
from elvion.core.contracts import ActionIntent
from elvion.planning.rules import UnsupportedCommand
from elvion.browser.session import public_url

APP = 'elvion.browser.chromium'
CAPABILITIES = frozenset({'web.open', 'web.search', 'web.open_result'})


def is_web_command(text):
    return re.match(r'^(?:mở\s+(?:web|trang|kết quả)|tìm\s+(?:trên\s+web|kiếm\s+trên\s+web))\b', text, re.I) is not None


def plan_web(request, *, session):
    text = request.utterance.strip()
    match = re.fullmatch(r'mở\s+(?:web|trang)\s+(https://\S+)', text, re.I)
    if match:
        capability, arguments = 'web.open', {'url':public_url(match[1])}
    else:
        match = re.fullmatch(r'tìm\s+(?:kiếm\s+)?trên\s+web\s+(.+)', text, re.I)
        if match and 1 <= len(match[1]) <= 512:
            capability, arguments = 'web.search', {'query':match[1]}
        else:
            match = re.fullmatch(r'mở\s+kết\s+quả\s+([1-9][0-9]?)', text, re.I)
            if not match or not 1 <= int(match[1]) <= len(session.results):
                raise UnsupportedCommand('Use explicit web command and current result number')
            handle, item = list(session.results.items())[int(match[1])-1]
            capability, arguments = 'web.open_result', {'handle':handle, 'url':public_url(item['url'])}
    return ActionIntent(task_id=request.task_id, capability=capability, target={'app':APP},
                        arguments=arguments, postcondition={'kind':'web_state', **arguments})


def valid_web_intent(intent, session):
    if (intent.target != {'app':APP} or intent.preconditions or intent.risk != 'low' or
            intent.capability not in CAPABILITIES or intent.postcondition != {'kind':'web_state', **intent.arguments}):
        return False
    args = intent.arguments
    if intent.capability == 'web.search':
        return set(args) == {'query'} and type(args['query']) is str and 1 <= len(args['query']) <= 512
    if set(args) != ({'url'} if intent.capability == 'web.open' else {'url', 'handle'}):
        return False
    try:
        public_url(args['url'])
    except ValueError:
        return False
    return intent.capability == 'web.open' or session.results.get(args.get('handle'), {}).get('url') == args['url']
