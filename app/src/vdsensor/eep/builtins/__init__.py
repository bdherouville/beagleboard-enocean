"""Auto-register every builtin EEP decoder when the package is imported."""

from __future__ import annotations

from ..decoder import register
from . import a5_02_05, a5_04_01, a5_07_01, a5_09_04, d5_00_01, f6_02_01

register("A5-02-05", a5_02_05.decode)
register("A5-04-01", a5_04_01.decode)
register("A5-07-01", a5_07_01.decode)
register("A5-09-04", a5_09_04.decode)
register("F6-02-01", f6_02_01.decode)
register("D5-00-01", d5_00_01.decode)
