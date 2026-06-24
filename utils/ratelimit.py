import time
import threading

import config

_lock = threading.Lock()
_last_request: dict[int, float] = {}


def check_rate_limit(user_id: int) -> tuple[bool, float]:
    """Returns (allowed, remaining_seconds).

    allowed is True if the user can make a request now, otherwise False and
    remaining_seconds tells how long to wait.
    """
    now = time.monotonic()
    with _lock:
        last = _last_request.get(user_id, 0.0)
        elapsed = now - last
        if elapsed < config.RATE_LIMIT_SECONDS:
            return False, config.RATE_LIMIT_SECONDS - elapsed
        _last_request[user_id] = now
        return True, 0.0