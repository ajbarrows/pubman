from __future__ import annotations

import importlib
from typing import Callable

from ..config import GeneratorConfig


def load_generator(config: GeneratorConfig) -> Callable:
    """Load a generator function from 'module' (calls 'generate') or 'module:function'."""
    module_str = config.module
    if ":" in module_str:
        module_name, func_name = module_str.rsplit(":", 1)
    else:
        module_name, func_name = module_str, "generate"

    module = importlib.import_module(module_name)
    return getattr(module, func_name)
