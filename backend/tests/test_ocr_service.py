import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ocr_service as o


class OcrServiceTests(unittest.TestCase):
    def setUp(self):
        o._cache.clear()

    def test_same_image_is_read_once(self):
        with mock.patch.object(o, "_read", return_value="text") as read:
            self.assertEqual(o.ocr_image(b"img"), "text")
            self.assertEqual(o.ocr_image(b"img"), "text")
        read.assert_called_once()

    def test_few_images_are_left_to_the_single_process_path(self):
        with mock.patch.object(o, "_run_worker") as worker:
            o.prefetch([b"a", b"b"])  # below OCR_PARALLEL_MIN (3)
        worker.assert_not_called()

    def test_many_images_run_in_workers_and_fill_the_cache(self):
        def fake_worker(share, threads):
            return {key: "ocr:" + data.decode() for key, data in share}
        images = [b"a", b"b", b"c", b"d", b"a"]  # one duplicate
        with mock.patch.object(o, "_run_worker", side_effect=fake_worker) as worker, \
                mock.patch.object(o, "_read", side_effect=AssertionError("should be cached")):
            o.prefetch(images)
            self.assertEqual([o.ocr_image(x) for x in (b"a", b"d")], ["ocr:a", "ocr:d"])
        shares = [call.args[0] for call in worker.call_args_list]
        self.assertEqual(sum(len(s) for s in shares), 4)  # duplicates sent once

    def test_cached_images_are_not_sent_to_workers_again(self):
        o._cache[o._digest(b"a")] = "done"
        with mock.patch.object(o, "_run_worker", return_value={}) as worker:
            o.prefetch([b"a", b"b", b"c"])  # only 2 new images, below the threshold
        worker.assert_not_called()

    def test_worker_failure_falls_back_instead_of_failing(self):
        with mock.patch.object(o, "_run_worker", side_effect=RuntimeError("boom")):
            o.prefetch([b"a", b"b", b"c"])  # must not raise
        with mock.patch.object(o, "_read", return_value="slow path"):
            self.assertEqual(o.ocr_image(b"a"), "slow path")


if __name__ == "__main__":
    unittest.main()
