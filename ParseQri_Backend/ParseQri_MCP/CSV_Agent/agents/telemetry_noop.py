from overrides import override

from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent


class NoopTelemetryClient(ProductTelemetryClient):
    """
    ChromaDB product telemetry no-op implementation.

    Your installed `posthog` package has an incompatible `capture()` signature,
    which causes ChromaDB telemetry to log errors. This client prevents any
    telemetry events from being sent/captured.
    """

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return

