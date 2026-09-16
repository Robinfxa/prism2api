"""Fail closed until a transport is explicitly supplied."""
from prism2api.transport.base import BaseTransport, AuthProfile

class UnconfiguredTransport(BaseTransport):
    kind = "unconfigured"
    def __init__(self):
        self.auth_profile = AuthProfile(profile_id="unconfigured")
    def inspect_capabilities(self, session):
        return []
    def submit(self, **kwargs):
        raise RuntimeError("No Prism transport configured")
    def observe_events(self, handle):
        raise RuntimeError("No Prism transport configured")
    def request_cancel(self, handle):
        raise RuntimeError("No Prism transport configured")
