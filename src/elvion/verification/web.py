from urllib.parse import urlsplit, parse_qs
from elvion.core.contracts import ObservationRequest, ObservationStatus
from elvion.planning.web import APP


def verify_web(intent, result, adapter):
    observation = adapter.observe(ObservationRequest(app=APP, kind='web_state', subject_id='active-page'))
    if observation.status != ObservationStatus.OBSERVED:
        return False
    state = observation.data
    if state.get('ready') is not True or not state.get('title'):
        return False
    if intent.capability == 'web.search':
        url = urlsplit(state.get('url', ''))
        return (url.scheme == 'https' and url.hostname == 'duckduckgo.com' and
                parse_qs(url.query).get('q') == [intent.arguments['query']] and state.get('visible_results', 0) > 0)
    return state.get('url', '').rstrip('/') == intent.arguments['url'].rstrip('/')
