# advanced_filter/__init__.py
# Cria aliases de submódulos para manter compatibilidade de imports
# sem precisar de arquivos duplicados (facades).

from importlib import import_module as _import_module
import sys as _sys

# Mapeia nomes antigos -> módulos reais
_ALIASES = {
    "engine":        "advanced_filter.core.engine",
    "preprocessor":  "advanced_filter.core.preprocessor",
    "matcher":       "advanced_filter.core.matcher",
    "decider":       "advanced_filter.core.decider",
    "resolver":      "advanced_filter.core.resolver",
    "scorer":        "advanced_filter.core.scorer",
    "dsl":           "advanced_filter.core.dsl",
    "config_loader": "advanced_filter.core.config_loader",
    "auditor":       "advanced_filter.core.auditor",
    "excel_io":      "advanced_filter.io.excel_io",
}

# Eager alias: registra os submódulos antigos apontando para os novos
# Isso garante que "from advanced_filter.engine import X" funcione.
for _name, _target in _ALIASES.items():
    _mod = _import_module(_target)
    _sys.modules[__name__ + "." + _name] = _mod
    globals()[_name] = _mod  # permite "import advanced_filter.engine as engine"

# Opcional: deixa a descoberta/auto-complete mais amigável
def __dir__():
    return sorted(list(globals().keys()) + list(_ALIASES.keys()))

__all__ = sorted(list(_ALIASES.keys()))
