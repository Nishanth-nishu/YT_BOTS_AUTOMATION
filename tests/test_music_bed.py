import numpy as np

from services.audio.make_music_bed import SR, make_bed


def test_music_bed_is_deterministic_and_quiet():
    a = make_bed(3, 84, seed=7)
    b = make_bed(3, 84, seed=7)
    assert a.shape == (3 * SR, 2)
    assert np.array_equal(a, b)
    peak = float(np.abs(a).max())
    assert peak < 0.2  # about -18 dBFS or lower, so it never fights the voice
    assert a[0].tolist() == [0.0, 0.0]  # fades in from silence
