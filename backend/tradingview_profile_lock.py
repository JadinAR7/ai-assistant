import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOCK_PATH = BASE_DIR / "tradingview_profile.lock"


class TradingViewProfileLockTimeout(TimeoutError):
    pass


@contextmanager
def tradingview_profile_lock(
    *,
    owner: str,
    timeout_seconds: float = 20,
    poll_seconds: float = 0.25,
    logs: list[str] | None = None,
):
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(timeout_seconds, 0)
    lock_file = LOCK_PATH.open("a+", encoding="utf-8")
    acquired = False

    def log(message: str) -> None:
        full_message = f"TradingView profile lock {message}"
        print(full_message)
        if logs is not None:
            logs.append(full_message)

    try:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                lock_file.seek(0)
                lock_file.truncate()
                lock_file.write(f"{owner} pid={os.getpid()} acquired_at={time.time()}\n")
                lock_file.flush()
                log(f"acquired by {owner}.")
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    log(f"busy; {owner} timed out after {timeout_seconds:g}s.")
                    raise TradingViewProfileLockTimeout(
                        f"TradingView profile lock busy; {owner} timed out after {timeout_seconds:g}s."
                    )
                time.sleep(poll_seconds)

        yield
    finally:
        if acquired:
            try:
                lock_file.seek(0)
                lock_file.truncate()
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                log(f"released by {owner}.")
            finally:
                lock_file.close()
        else:
            lock_file.close()
