from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")


class PluginApp(PluginConfig):
    default = True
    name = "pretix_square"
    verbose_name = "Pretix Square Integration"

    class PretixPluginMeta:
        name = gettext_lazy("Pretix Square Integration")
        author = "Chris Cerne"
        description = gettext_lazy("Accept payments via Square.")
        visible = True
        version = __version__
        category = "PAYMENT"
        compatibility = "pretix>=2.7.0"

    def ready(self):
        from . import signals  # NOQA

    def is_available(self, event=None):
        return True
