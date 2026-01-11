# FF Bidding App Package
# Supports both AYON addon mode and standalone mode

__all__ = []

# Only import the addon if ayon_core is available (not in standalone mode)
try:
    from .addon import FFPackageManagerAddon
    __all__.append("FFPackageManagerAddon")
except ImportError:
    # Running in standalone mode without AYON
    pass

# Always export the main app class for standalone use
try:
    from .app import PackageManagerApp
    __all__.append("PackageManagerApp")
except ImportError:
    pass
