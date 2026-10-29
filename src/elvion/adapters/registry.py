"""Resolve adapters by descriptor ID and validate probes before selection."""
from elvion.core.adapter import Adapter
from elvion.core.contracts import ActionIntent, CapabilityDescriptor, ContractError, ProbeResult


class AdapterRegistry:
    def __init__(self, adapters: tuple[Adapter, ...] = ()):
        self._adapters: dict[str, Adapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: Adapter) -> None:
        if not isinstance(adapter, Adapter) or not isinstance(adapter.descriptor, CapabilityDescriptor):
            raise ContractError("Adapter must implement the common protocol and descriptor")
        name = adapter.descriptor.name
        if name in self._adapters:
            raise ContractError("Adapter ID is already registered")
        self._adapters[name] = adapter

    def get(self, adapter_id: str) -> Adapter:
        return self._adapters[adapter_id]

    def all(self) -> tuple[Adapter, ...]:
        return tuple(self._adapters.values())

    def probe(self, intent: ActionIntent, grants: frozenset[str]) -> list[ProbeResult]:
        probes = []
        for name, adapter in self._adapters.items():
            descriptor = adapter.descriptor
            supported = (intent.capability in descriptor.supported_actions
                         and intent.target.get("app") == descriptor.app)
            reason = None
            if not supported:
                reason = "DESCRIPTOR_UNSUPPORTED"
            elif not set(descriptor.required_permissions).issubset(grants):
                reason = "ADAPTER_PERMISSION_DENIED"
            elif not descriptor.can_verify:
                reason = "VERIFICATION_UNAVAILABLE"
            else:
                try:
                    probe = adapter.probe(intent)
                    if (not isinstance(probe, ProbeResult) or probe.adapter_id != name
                            or probe.method != descriptor.method):
                        raise ContractError("Probe does not match descriptor")
                except Exception:
                    # Never expose exception text, which might contain credentials.
                    reason = "ADAPTER_PROBE_FAILED"
                else:
                    probes.append(probe)
                    continue
            probes.append(ProbeResult(adapter_id=name, method=descriptor.method,
                                      supported=supported, prerequisites_met=False, reason=reason))
        return probes
