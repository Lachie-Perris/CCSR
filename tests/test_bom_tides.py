"""Validate BOM timestamp pairing, coverage and rejection of bad responses."""
import unittest

import pandas as pd

from bom_tides import parse_predictions


class BomChecks(unittest.TestCase):
    def table(self):
        stamps = pd.date_range('2026-10-03T12:00Z', periods=5, freq='6h')
        return ''.join(
            f'<td data-time-utc="{stamp.isoformat()}" '
            f'data-time-local="{stamp.tz_convert("Australia/Sydney").isoformat()}">Time</td>'
            f'<td class="height high-tide">{height} m</td>'
            for stamp, height in zip(stamps, [.5, 1.5, .6, 1.6, .5]))

    def test_dst_and_explicit_utc(self):
        events = parse_predictions(self.table(), '2026-10-03T13:00Z', '2026-10-04T11:00Z')
        self.assertEqual(len(events), 5)
        self.assertTrue(events.time_local.iloc[0].endswith('+10:00'))
        self.assertTrue(events.time_local.iloc[1].endswith('+11:00'))
        self.assertEqual(events.height_m.tolist(), [.5, 1.5, .6, 1.6, .5])

    def test_reject_incomplete_or_expired_data(self):
        for html in ['XML data not found.', self.table().replace('1.5 m', '1.5 ft'),
                     self.table().replace('1.5 m', ''), self.table() + self.table()]:
            with self.assertRaises(ValueError):
                parse_predictions(html, '2026-10-03T13:00Z', '2026-10-04T11:00Z')
        with self.assertRaises(ValueError):
            parse_predictions(self.table(), '2026-10-10T00:00Z', '2026-10-12T00:00Z')


if __name__ == '__main__':
    unittest.main()
