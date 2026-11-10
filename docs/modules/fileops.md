# core.fileops

Small helpers so the rest of the code doesn't care about the OS.

```python
from core.fileops import get_fileops
fops = get_fileops()            # Windows / Linux / macOS implementation, picked automatically
```

| Method | |
|---|---|
| `read_json(path)` / `write_json(path, data)` | |
| `read_toml(path)` / `write_toml(path, data)` | |
| `append_line(path, line)` | creates folders as needed (used by the recorder / JSONL logger) |
| `ensure_dir(path)` | `mkdir -p`, returns the path |
| `join(*parts)` | `Path` |
| `project_log_dir(project_root, subfolder)` | `<project>/logs/<subfolder>`, created |
| `platform_name()` | e.g. `windows-amd64`, `linux-x86_64`, `darwin-arm64` |

Errors are raised as the classes in `core/fileops/errors.py`.
