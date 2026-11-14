"""disc_meta:内部序列号解析(合成镜像,不触网、不依赖真实 ROM)。"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from batoroms import disc_meta
from tests import synthetic


class ReadSerialTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, data: bytes) -> Path:
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_psx_cooked_iso(self) -> None:
        p = self._write("game.iso", synthetic.make_iso9660("SLUS_005.94"))
        self.assertEqual(disc_meta.read_serial("psx", p), "SLUS-00594")

    def test_psx_raw2352_bin(self) -> None:
        data = synthetic.make_iso9660("SCES_123.45", sector_size=2352, data_off=24)
        p = self._write("game.bin", data)
        self.assertEqual(disc_meta.read_serial("psx", p), "SCES-12345")

    def test_ps2_uses_same_iso_path(self) -> None:
        p = self._write("game.iso", synthetic.make_iso9660("SLUS_200.62"))
        self.assertEqual(disc_meta.read_serial("ps2", p), "SLUS-20062")

    def test_cue_resolves_referenced_bin(self) -> None:
        self._write("game.bin", synthetic.make_iso9660("SLPS_001.00"))
        cue = self._write(
            "game.cue",
            b'FILE "game.bin" BINARY\n  TRACK 01 MODE2/2352\n',
        )
        self.assertEqual(disc_meta.read_serial("psx", cue), "SLPS-00100")

    def test_saturn_product(self) -> None:
        p = self._write("sat.bin", synthetic.make_saturn("MK-81304  "))
        self.assertEqual(disc_meta.read_serial("saturn", p), "MK-81304")

    def test_dreamcast_product(self) -> None:
        p = self._write("dc.bin", synthetic.make_dreamcast("MK-51035  "))
        self.assertEqual(disc_meta.read_serial("dreamcast", p), "MK-51035")

    def test_megacd_serial(self) -> None:
        p = self._write("mcd.bin", synthetic.make_megacd("GM T-50015 -00"))
        self.assertEqual(disc_meta.read_serial("megacd", p), "T-50015")

    def test_psp_umd_data_bin(self) -> None:
        p = self._write("game.iso", synthetic.make_psp("ULUS-10041"))
        self.assertEqual(disc_meta.read_serial("psp", p), "ULUS-10041")

    def test_psp_gamecode_without_dash(self) -> None:
        p = self._write("game.iso", synthetic.make_psp("ULES00151"))
        self.assertEqual(disc_meta.read_serial("psp", p), "ULES-00151")

    def test_psp_raw2352(self) -> None:
        data = synthetic.make_psp("NPUG-80086", sector_size=2352, data_off=24)
        p = self._write("game.bin", data)
        self.assertEqual(disc_meta.read_serial("psp", p), "NPUG-80086")

    def test_unsupported_system_returns_none(self) -> None:
        p = self._write("x.iso", synthetic.make_iso9660("SLUS_005.94"))
        self.assertIsNone(disc_meta.read_serial("3do", p))

    def test_garbage_returns_none(self) -> None:
        p = self._write("junk.iso", b"\x00" * 4096)
        self.assertIsNone(disc_meta.read_serial("psx", p))

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(disc_meta.read_serial("psx", self.dir / "nope.iso"))

    def _zip(self, name: str, members: dict[str, bytes]) -> Path:
        p = self.dir / name
        with zipfile.ZipFile(p, "w") as zf:
            for member, data in members.items():
                zf.writestr(member, data)
        return p

    def test_dreamcast_zip_gdi_tracks(self) -> None:
        gdi = b"3\n1 0 4 2352 track01.bin 0\n2 600 0 2352 track02.raw 0\n3 45000 4 2352 track03.iso 0\n"
        p = self._zip(
            "Game (USA).zip",
            {
                "Game/disc.gdi": gdi,
                "Game/track01.bin": b"\x00" * 1024,
                "Game/track02.raw": b"\x00" * 1024,
                "Game/track03.iso": synthetic.make_dreamcast("MK-51035  "),
            },
        )
        self.assertEqual(disc_meta.read_serial("dreamcast", p), "MK-51035")

    def test_zip_without_primary_returns_none(self) -> None:
        p = self._zip("x.zip", {"readme.txt": b"hi"})
        self.assertIsNone(disc_meta.read_serial("dreamcast", p))

    def test_bad_zip_returns_none(self) -> None:
        p = self._write("bad.zip", b"not a zip")
        self.assertIsNone(disc_meta.read_serial("dreamcast", p))

    def test_zip_primary_member_rules(self) -> None:
        pick = disc_meta.zip_primary_member
        self.assertEqual(pick(["a/disc.gdi", "a/track03.iso"]), "a/disc.gdi")
        self.assertEqual(pick(["game.iso"]), "game.iso")
        with self.assertRaises(ValueError):
            pick(["d1.gdi", "d2.gdi"])
        with self.assertRaises(ValueError):
            pick(["readme.txt"])


if __name__ == "__main__":
    unittest.main()
