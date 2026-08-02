"""
Windows: subprocess helpers so yt-dlp children (ffmpeg, etc.) cannot outlive a download.

Uses a job object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE so closing the job handle
terminates every process still in the job -- covering orphans when the parent exits first.
Also exposes taskkill /T for explicit cancellation.
"""
from __future__ import annotations

import ctypes
import logging
import subprocess as sp
import sys
from ctypes import wintypes

logger = logging.getLogger(__name__)

_WIN_NO_WINDOW = sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0

if sys.platform != "win32":
    WinDownloadJob = None  # type: ignore[misc, assignment]

    def kill_windows_process_tree(pid: int) -> None:
        return

else:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JobObjectExtendedLimitInformation = 9

    PROCESS_TERMINATE = 0x0001
    PROCESS_SET_QUOTA = 0x0100

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = (
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        )

    _ulonglong = ctypes.c_ulonglong

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = (
            ("ReadOperationCount", _ulonglong),
            ("WriteOperationCount", _ulonglong),
            ("OtherOperationCount", _ulonglong),
            ("ReadTransferCount", _ulonglong),
            ("WriteTransferCount", _ulonglong),
            ("OtherTransferCount", _ulonglong),
        )

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = (
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        )

    _CreateJobObjectW = kernel32.CreateJobObjectW
    _CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _CreateJobObjectW.restype = wintypes.HANDLE

    _SetInformationJobObject = kernel32.SetInformationJobObject
    _SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _SetInformationJobObject.restype = wintypes.BOOL

    _AssignProcessToJobObject = kernel32.AssignProcessToJobObject
    _AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _AssignProcessToJobObject.restype = wintypes.BOOL

    _OpenProcess = kernel32.OpenProcess
    _OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _OpenProcess.restype = wintypes.HANDLE

    _CloseHandle = kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL

    def _create_kill_on_close_job() -> int | None:
        job = _CreateJobObjectW(None, None)
        if not job:
            logger.warning("CreateJobObjectW failed: %s", ctypes.WinError(ctypes.get_last_error()))
            return None
        ext = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        ext.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = _SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(ext),
            ctypes.sizeof(ext),
        )
        if not ok:
            logger.warning("SetInformationJobObject failed: %s", ctypes.WinError(ctypes.get_last_error()))
            _CloseHandle(job)
            return None
        return job

    def _assign_pid(job: int, pid: int) -> bool:
        access = PROCESS_TERMINATE | PROCESS_SET_QUOTA
        hproc = _OpenProcess(access, False, pid)
        if not hproc:
            logger.warning("OpenProcess(pid=%s) failed: %s", pid, ctypes.WinError(ctypes.get_last_error()))
            return False
        try:
            if not _AssignProcessToJobObject(job, hproc):
                logger.warning(
                    "AssignProcessToJobObject(pid=%s) failed: %s",
                    pid,
                    ctypes.WinError(ctypes.get_last_error()),
                )
                return False
        finally:
            _CloseHandle(hproc)
        return True

    class WinDownloadJob:
        __slots__ = ("_handle",)

        def __init__(self) -> None:
            self._handle: int | None = _create_kill_on_close_job()

        def assign(self, pid: int) -> None:
            if self._handle is None or pid <= 0:
                return
            _assign_pid(self._handle, pid)

        def close(self) -> None:
            if self._handle is not None:
                _CloseHandle(self._handle)
                self._handle = None

        def __enter__(self) -> "WinDownloadJob":
            return self

        def __exit__(self, *_exc) -> None:
            self.close()

    def kill_windows_process_tree(pid: int) -> None:
        if pid <= 0:
            return
        try:
            sp.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
                creationflags=_WIN_NO_WINDOW,
                timeout=45,
                check=False,
            )
        except Exception:
            logger.exception("taskkill /T failed for pid=%s", pid)
