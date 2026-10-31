import json
import logging
from dataclasses import asdict, dataclass, fields
from .paths import data_dir


@dataclass
class Settings:
    port: int = 8765
    host: str = "0.0.0.0"
    advertised_host: str = ""
    theme: str = "system"
    auto_start: bool = False
    gain: float = 1.0
    device_id: int | None = None
    tls_cert: str = ""
    tls_key: str = ""
    check_updates: bool = True
    language: str = "ko"

    @classmethod
    def load(cls):
        try:
            raw = json.loads((data_dir() / "settings.json").read_text(encoding="utf-8"))
            obj = cls(**{f.name: raw[f.name] for f in fields(cls) if f.name in raw})
            if type(obj.port) is not int or not 1024 <= obj.port <= 65535:
                raise ValueError("Invalid port")
            obj.gain = max(0.0, min(2.0, float(obj.gain)))
            if obj.theme not in ("system", "light", "dark"):
                obj.theme = "system"
            return obj
        except FileNotFoundError:
            return cls()
        except (ValueError, TypeError, OSError):
            logging.getLogger(__name__).warning("Settings unreadable; defaults restored")
            return cls()

    def save(self):
        target = data_dir() / "settings.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
