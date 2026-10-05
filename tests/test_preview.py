"""Publishing must work with either model and refuse an empty deployment."""
from pathlib import Path
import tempfile
import unittest

from build_preview import build_page


class PreviewChecks(unittest.TestCase):
    def test_model_availability(self):
        for models in [('ec',), ('gfs',), ('ec', 'gfs')]:
            with self.subTest(models=models), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                for model in models:
                    (folder / f'{model}_forecast.png').write_bytes(b'fixture')
                page = build_page(folder).read_text()
                self.assertIn('This week', page)
                self.assertIn('The weekend', page)
                self.assertIn('coming soon', page)
                for model in ['ec', 'gfs']:
                    self.assertIn(f'id="{model}"', page)
                    self.assertEqual(f'"{model}_forecast.png"' in page, model in models)
                self.assertNotIn('__DEFAULT__', page)

    def test_empty_or_zero_byte_output_shows_coming_soon(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'ec_forecast.png').touch()
            page = build_page(folder).read_text()
            self.assertIn('"week": {}, "weekend": {}', page)
            self.assertIn('coming soon', page)

    def test_full_view_is_independent_of_weekend(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'gfs_week_forecast.png').write_bytes(b'fixture')
            page = build_page(folder).read_text()
            self.assertIn('"week": {"gfs": "gfs_week_forecast.png"}', page)
            self.assertIn('"weekend": {}', page)
