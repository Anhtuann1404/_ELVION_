from elvion.policy.rules import CapabilityPolicy
from elvion.planning.web import valid_web_intent


class WebPolicy(CapabilityPolicy):
    version = 'browser-web-v1'

    def __init__(self, session):
        super().__init__(require_confirmation=True)
        self.session = session

    def allows(self, intent, grants):
        return intent.capability in grants and valid_web_intent(intent, self.session)

    def confirmation_effects(self, intent):
        return ('Send the approved URL or search query to the public web in an isolated browser',)
