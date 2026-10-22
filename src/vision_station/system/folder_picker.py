"""The folder chooser of the operating system, opened on the PC that runs the program (VIA-0122).

The interface runs in a browser, which never gives a program the path of a folder, so the program asks Windows
itself and sends the path back. It is only for the person at the station PC (the API says no when it listens on
the network). Windows only; elsewhere `available()` is False and the screen shows no button. The one OS-specific
part of `system/` (design rule 7): it uses nothing but `ctypes`, so it adds no dependency to the install.
"""

import sys
import threading
from pathlib import Path


def available() -> bool:
    return sys.platform == "win32"


def pick_folder(initial: str | None = None) -> str | None:
    """Show the chooser and wait. The chosen folder, or None when the person cancelled. Runs in its own thread:
    a Windows dialog needs a thread that has initialised COM and that nothing else is using."""
    if not available():
        raise OSError("the folder chooser needs Windows")
    out: list[str | None] = []
    failed: list[BaseException] = []

    def run() -> None:
        try:
            out.append(_windows_chooser(initial))
        except BaseException as exc:  # a broken chooser must not look like a cancelled one
            failed.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join()
    if failed:
        raise OSError(f"the folder chooser failed: {failed[0]}") from failed[0]
    return out[0]


def _windows_chooser(initial: str | None) -> str | None:  # pragma: no cover - needs a Windows desktop
    """The Explorer-style chooser (`IFileOpenDialog` in folder mode), called through its COM table with `ctypes`."""
    import ctypes
    from ctypes import wintypes

    ole32, shell32, user32 = ctypes.windll.ole32, ctypes.windll.shell32, ctypes.windll.user32  # type: ignore[attr-defined]
    FOS_PICKFOLDERS, FOS_FORCEFILESYSTEM, SIGDN_FILESYSPATH = 0x20, 0x40, 0x80058000
    CANCELLED = 0x800704C7  # HRESULT_FROM_WIN32(ERROR_CANCELLED)

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]

    def guid(text: str) -> GUID:
        out = GUID()
        ole32.CLSIDFromString(text, ctypes.byref(out))
        return out

    def method(obj: ctypes.c_void_p, index: int, *argtypes):
        table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(table[index])

    def check(code: int) -> int:
        if code < 0 and (code & 0xFFFFFFFF) != CANCELLED:
            raise OSError(f"HRESULT 0x{code & 0xFFFFFFFF:08X}")
        return code

    ole32.CoInitialize(None)
    dialog = ctypes.c_void_p()
    try:
        check(ole32.CoCreateInstance(
            ctypes.byref(guid("{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}")), None, 1,  # CLSID_FileOpenDialog, in-process
            ctypes.byref(guid("{d57c7288-d4ad-4768-be02-9d969532d960}")), ctypes.byref(dialog)))  # IID_IFileOpenDialog
        # vtable: Show 3, SetOptions 9, GetOptions 10, SetFolder 12, GetResult 20, Release 2
        options = wintypes.DWORD()
        check(method(dialog, 10, ctypes.POINTER(wintypes.DWORD))(dialog, ctypes.byref(options)))
        check(method(dialog, 9, wintypes.DWORD)(dialog, options.value | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM))
        if initial and Path(initial).is_dir():  # open on the folder that is there now
            start = ctypes.c_void_p()
            if shell32.SHCreateItemFromParsingName(str(Path(initial)), None, ctypes.byref(guid("{43826d1e-e718-42ee-bc55-a1e261c37bfe}")), ctypes.byref(start)) >= 0:
                method(dialog, 12, ctypes.c_void_p)(dialog, start)
                method(start, 2)(start)
        if check(method(dialog, 3, wintypes.HWND)(dialog, user32.GetForegroundWindow())) < 0:  # over the browser, not behind it
            return None  # cancelled
        item = ctypes.c_void_p()
        check(method(dialog, 20, ctypes.POINTER(ctypes.c_void_p))(dialog, ctypes.byref(item)))
        if not item:
            return None  # closed without choosing
        try:
            name = ctypes.c_wchar_p()
            check(method(item, 5, wintypes.DWORD, ctypes.POINTER(ctypes.c_wchar_p))(item, SIGDN_FILESYSPATH, ctypes.byref(name)))  # IShellItem.GetDisplayName
            path = name.value
            ole32.CoTaskMemFree(ctypes.cast(name, ctypes.c_void_p))
            return path
        finally:
            method(item, 2)(item)
    finally:
        if dialog:
            method(dialog, 2)(dialog)
        ole32.CoUninitialize()
