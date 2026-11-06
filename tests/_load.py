"""Load helper scripts by file path (skill folders contain hyphens, so normal imports fail)."""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"


def load(skill: str, script: str):
    """Import skills/<skill>/<script>.py as a module and return it."""
    path = SKILLS / skill / f"{script}.py"
    name = f"_maintainer_{script}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
