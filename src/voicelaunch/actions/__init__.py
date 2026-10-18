from dataclasses import dataclass
@dataclass(frozen=True)
class ActionResult: ok: bool; message: str
