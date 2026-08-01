from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from .validator import validate_output_dir


def package_output(
    output_dir: str | Path,
    zip_path: str | Path,
    input_dir: str | Path | None = None,
    position_mode: str = "raw",
) -> dict[str, Any]:
    output = Path(output_dir)
    if input_dir is not None:
        validation = validate_output_dir(input_dir, output, position_mode)
        if not validation["ok"]:
            raise ValueError(json.dumps(validation, ensure_ascii=False))
    files = sorted(output.glob("*.json"), key=lambda p: int(p.stem))
    if not files:
        raise ValueError(f"no JSON files in {output}")
    target = Path(zip_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            # Stable metadata makes identical output directories produce an
            # identical submission archive across runs and machines.
            info = zipfile.ZipInfo(
                filename=f"output/{path.name}",
                date_time=(2020, 1, 1, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return {"zip": str(target), "files": len(files), "members": [f"output/{p.name}" for p in files]}
