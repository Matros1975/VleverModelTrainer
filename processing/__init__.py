# Compatibility shim: torchaudio 2.x removed torchaudio.backend.common.
# deepfilternet 0.5.x imports AudioMetaData from there as a type annotation only,
# so a stub module is enough to satisfy the import before df is first loaded.
import sys
import types

if "torchaudio.backend" not in sys.modules:
    _backend_pkg = types.ModuleType("torchaudio.backend")
    _backend_common = types.ModuleType("torchaudio.backend.common")
    _backend_common.AudioMetaData = object  # type: ignore[attr-defined]
    sys.modules["torchaudio.backend"] = _backend_pkg
    sys.modules["torchaudio.backend.common"] = _backend_common
