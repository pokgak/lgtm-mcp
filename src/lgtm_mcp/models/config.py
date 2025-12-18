"""Pydantic models for configuration."""

from pydantic import BaseModel, Field


class BackendConfig(BaseModel):
    """Configuration for a single backend (Loki, Prometheus, or Tempo)."""

    url: str = Field(..., description="Base URL for the backend API")
    token: str | None = Field(None, description="Bearer token for authentication")
    headers: dict[str, str] = Field(default_factory=dict, description="Additional headers")
    timeout: int = Field(30, description="Request timeout in seconds")


class InstanceConfig(BaseModel):
    """Configuration for a single LGTM instance."""

    loki: BackendConfig | None = None
    prometheus: BackendConfig | None = None
    tempo: BackendConfig | None = None


class Settings(BaseModel):
    """Global settings for the MCP server."""

    max_log_entries: int = Field(1000, description="Maximum log entries to return")
    max_metric_samples: int = Field(10000, description="Maximum metric samples to return")
    max_traces: int = Field(100, description="Maximum traces to return")
    max_connections: int = Field(100, description="Maximum HTTP connections per pool")
    max_keepalive_connections: int = Field(20, description="Max keepalive connections")
    keepalive_expiry: int = Field(30, description="Keepalive expiry in seconds")


class LGTMConfig(BaseModel):
    """Root configuration model."""

    version: str = Field("1", description="Config schema version")
    default_instance: str = Field(..., description="Default instance name to use")
    instances: dict[str, InstanceConfig] = Field(..., description="Named LGTM instances")
    settings: Settings = Field(default_factory=Settings, description="Global settings")

    def get_instance(self, name: str | None = None) -> InstanceConfig:
        """Get an instance by name, falling back to default."""
        instance_name = name or self.default_instance
        if instance_name not in self.instances:
            raise ValueError(f"Unknown instance: {instance_name}")
        return self.instances[instance_name]

    def get_loki(self, instance: str | None = None) -> BackendConfig:
        """Get Loki backend config for an instance."""
        inst = self.get_instance(instance)
        if inst.loki is None:
            raise ValueError(
                f"Loki not configured for instance: {instance or self.default_instance}"
            )
        return inst.loki

    def get_prometheus(self, instance: str | None = None) -> BackendConfig:
        """Get Prometheus backend config for an instance."""
        inst = self.get_instance(instance)
        if inst.prometheus is None:
            raise ValueError(
                f"Prometheus not configured for instance: {instance or self.default_instance}"
            )
        return inst.prometheus

    def get_tempo(self, instance: str | None = None) -> BackendConfig:
        """Get Tempo backend config for an instance."""
        inst = self.get_instance(instance)
        if inst.tempo is None:
            raise ValueError(
                f"Tempo not configured for instance: {instance or self.default_instance}"
            )
        return inst.tempo
