import os
import sys
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """Devuelve la ruta absoluta a un recurso del proyecto.

    En modo script usa la carpeta del proyecto actual.
    En modo empaquetado (.exe) busca el recurso en el directorio temporal
    de la app (como sys._MEIPASS), en la carpeta del ejecutable o en la
    carpeta del proyecto. Esto cubre PyInstaller, py2exe y Nuitka.
    """
    if getattr(sys, "frozen", False):
        candidates = []

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))

        executable = getattr(sys, "executable", None)
        if executable:
            candidates.append(Path(executable).resolve().parent)

        argv0 = sys.argv[0] if sys.argv else None
        if argv0:
            candidates.append(Path(argv0).resolve().parent)

        for base_path in candidates:
            path = base_path / relative_path
            if path.exists():
                return str(path.resolve())

        base_path = candidates[0] if candidates else Path(os.path.abspath("."))
    else:
        base_path = Path(__file__).resolve().parent

    path = base_path / relative_path
    return str(path.resolve())