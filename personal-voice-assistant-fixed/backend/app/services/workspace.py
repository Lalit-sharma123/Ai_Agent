from pathlib import Path
from ..config import get_settings

class WorkspaceError(ValueError):
    pass

def allowed_roots() -> list[Path]:
    settings = get_settings()
    roots = []
    for raw in settings.workspace_roots.split(","):
        raw = raw.strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        else:
            path = path.resolve()
        roots.append(path)
    if not roots:
        roots = [(Path.cwd() / "workspace").resolve()]
    return roots

def resolve_workspace_path(raw: str = ".") -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (allowed_roots()[0] / candidate).resolve()
    else:
        candidate = candidate.resolve()
    for root in allowed_roots():
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    raise WorkspaceError("Path is outside configured WORKSPACE_ROOTS.")
