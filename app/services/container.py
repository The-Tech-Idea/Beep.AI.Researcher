"""Simple dependency injection container.

Usage:
    # Register a service (transient — new instance each get)
    Container.register(UserService, lambda: UserService(Container.get(UserRepository)))

    # Register a singleton (one instance shared)
    Container.register(ConfigManager, lambda: config_manager, singleton=True)

    # Get a service
    service = Container.get(UserService)

    # Reset (for testing)
    Container.reset()

This is intentionally lightweight — no third-party DI framework needed.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Type


class Container:
    """Lightweight dependency injection container."""

    _factories: Dict[Type, Callable[[], Any]] = {}
    _singletons: Dict[Type, Any] = {}

    @classmethod
    def register(
        cls,
        interface: Type,
        factory: Callable[[], Any],
        *,
        singleton: bool = False,
    ) -> None:
        """Register a service factory.

        Args:
            interface: The type/interface to register under.
            factory: A callable that creates the service instance.
            singleton: If True, the instance is created once and cached.
        """
        cls._factories[interface] = factory
        if singleton:
            cls._singletons[interface] = factory()

    @classmethod
    def get(cls, interface: Type) -> Any:
        """Resolve a service by its interface type.

        Args:
            interface: The type to resolve.

        Returns:
            The service instance.

        Raises:
            KeyError: If the interface is not registered.
        """
        if interface in cls._singletons and cls._singletons[interface] is not None:
            return cls._singletons[interface]
        if interface not in cls._factories:
            raise KeyError(f"Service {interface.__name__} not registered in container")
        return cls._factories[interface]()

    @classmethod
    def has(cls, interface: Type) -> bool:
        """Check if a service is registered."""
        return interface in cls._factories or interface in cls._singletons

    @classmethod
    def reset(cls) -> None:
        """Clear all registrations — for testing."""
        cls._factories.clear()
        cls._singletons.clear()
