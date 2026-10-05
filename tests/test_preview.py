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
                self.assertIn(f'src="{models[0]}_forecast.png"', page)
                self.assertIn(f'download="surf-forecast-{models[0]}.png"', page)
                for model in ['ec', 'gfs']:
                    self.assertEqual(f'id="{model}"' in page, model in models)
                self.assertNotIn('__DEFAULT__', page)

    def test_empty_or_zero_byte_output_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'ec_forecast.png').touch()
            with self.assertRaises(FileNotFoundError):
                build_page(folder)
            self.assertFalse((folder / 'index.html').exists())
