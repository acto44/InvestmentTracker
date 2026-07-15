"""API-key storage. On Windows the key is encrypted at rest with DPAPI
(CryptProtectData, per-user scope — stdlib ctypes, no dependency): only
this Windows user on this machine can decrypt it. On other OSes we fall
back to reversible obfuscation and storage_is_encrypted() returns False —
the settings UI MUST surface that as a warning.

The key lives in a file under the user profile (never in the database:
the DB gets backed up and must not carry credentials) and never in the
repo. Tests point the store at a temp dir via set_store_dir()."""

from __future__ import annotations

import base64
import os
import sys

_MAGIC_DPAPI = b'DPAPI1\n'
_MAGIC_OBF = b'OBF1\n'
_KEY_FILE = 'openai_key.bin'
# fixed local pad for the fallback — deliberately trivial; the point of
# the OBF path is "not plaintext on disk", NOT security (UI warns).
_OBF_PAD = b'family-investment-tracker-local-store'

_store_dir_override: str | None = None


def set_store_dir(path: str | None):
    """Test hook (mirrors models.set_db_path): None restores the default."""
    global _store_dir_override
    _store_dir_override = path


def _store_dir() -> str:
    if _store_dir_override:
        return _store_dir_override
    base = os.environ.get('APPDATA') or os.path.join(
        os.path.expanduser('~'), '.config')
    return os.path.join(base, 'FamilyInvestmentTracker', 'ai')


def _key_path() -> str:
    return os.path.join(_store_dir(), _KEY_FILE)


def _dpapi_available() -> bool:
    return sys.platform == 'win32'


# ── DPAPI via ctypes (Windows only) ──────────────────────────────────────────

def _dpapi_call(func_name: str, data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD),
                    ('pbData', ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    blob_in = DATA_BLOB(len(data),
                        ctypes.cast(ctypes.create_string_buffer(data,
                                                                len(data)),
                                    ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    fn = getattr(crypt32, func_name)
    ok = fn(ctypes.byref(blob_in), None, None, None, None,
            CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out))
    if not ok:
        raise OSError(f'{func_name} failed '
                      f'(WinError {ctypes.get_last_error()})')
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _protect(data: bytes) -> bytes:
    return _dpapi_call('CryptProtectData', data)


def _unprotect(blob: bytes) -> bytes:
    return _dpapi_call('CryptUnprotectData', blob)


# ── fallback obfuscation (non-Windows dev machines) ─────────────────────────

def _obfuscate(data: bytes) -> bytes:
    xored = bytes(b ^ _OBF_PAD[i % len(_OBF_PAD)]
                  for i, b in enumerate(data))
    return base64.b64encode(xored)


def _deobfuscate(blob: bytes) -> bytes:
    xored = base64.b64decode(blob)
    return bytes(b ^ _OBF_PAD[i % len(_OBF_PAD)]
                 for i, b in enumerate(xored))


# ── public API ───────────────────────────────────────────────────────────────

def storage_is_encrypted() -> bool:
    """True when keys are protected by DPAPI; False on the fallback path
    (the UI shows a 'not securely encrypted on this OS' warning)."""
    return _dpapi_available()


def save_api_key(key: str):
    os.makedirs(_store_dir(), exist_ok=True)
    raw = key.encode('utf-8')
    if _dpapi_available():
        payload = _MAGIC_DPAPI + _protect(raw)
    else:
        payload = _MAGIC_OBF + _obfuscate(raw)
    path = _key_path()
    with open(path, 'wb') as f:
        f.write(payload)
    if os.name == 'posix':
        os.chmod(path, 0o600)


def load_api_key() -> str | None:
    """The stored key, or None if absent/undecryptable (e.g. the file was
    copied from another Windows user — DPAPI correctly refuses)."""
    path = _key_path()
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        payload = f.read()
    try:
        if payload.startswith(_MAGIC_DPAPI):
            return _unprotect(payload[len(_MAGIC_DPAPI):]).decode('utf-8')
        if payload.startswith(_MAGIC_OBF):
            return _deobfuscate(payload[len(_MAGIC_OBF):]).decode('utf-8')
    except Exception:
        return None
    return None


def has_api_key() -> bool:
    return load_api_key() is not None


def clear_api_key():
    path = _key_path()
    if os.path.isfile(path):
        os.remove(path)
