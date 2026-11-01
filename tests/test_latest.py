import threading

from cipfried.core.latest import LatestValue


def test_latest_value_keeps_only_the_newest_value() -> None:
    latest: LatestValue[int] = LatestValue()

    assert latest.get() is None
    assert latest.set(1) == 1
    assert latest.set(2) == 2
    assert latest.get() == 2
    assert latest.snapshot() == (2, 2)


def test_latest_value_wait_next_times_out() -> None:
    latest: LatestValue[int] = LatestValue()

    assert latest.wait_next(0, timeout=0.01) is None


def test_latest_value_wait_next_wakes_on_new_value() -> None:
    latest: LatestValue[int] = LatestValue()
    timer = threading.Timer(0.01, lambda: latest.set(5))
    timer.start()

    try:
        result = latest.wait_next(0, timeout=1.0)
    finally:
        timer.cancel()

    assert result == (1, 5)


def test_latest_value_clear_advances_version_and_empties_slot() -> None:
    latest: LatestValue[int] = LatestValue(1)
    version = latest.version

    latest.clear()

    assert latest.get() is None
    assert latest.version == version + 1
