"""Check GFS field mapping and the inclusive two-day forecast window."""
import unittest
from unittest.mock import patch

import pandas as pd

from gfs_forecast import fetch_gfs_forecast
from forecast_plot import surf_height_band, weekend_window, daylight_means


class GfsChecks(unittest.TestCase):
    def test_friday_selects_weekend_across_dst(self):
        start, end = weekend_window('2026-10-02T12:00:00+10:00')
        self.assertEqual(start.strftime('%Y-%m-%d %H:%M'), '2026-10-03 00:00')
        self.assertEqual(end.strftime('%Y-%m-%d %H:%M'), '2026-10-05 00:00')
        self.assertEqual((end - start).total_seconds() / 3600, 47)
        index = pd.date_range(start, end, freq='h')
        frame = pd.DataFrame({'nearshore_height_ft': [2 if t.day == 3 else 5 for t in index]}, index=index)
        self.assertEqual(daylight_means(frame, start), [(2, 2), (5, 5)])

    def test_missing_height_is_not_large_surf(self):
        self.assertEqual(surf_height_band(float('nan')), '—')

    @patch('gfs_forecast.transform_waves', side_effect=lambda frame: frame)
    @patch('gfs_forecast._get')
    def test_peak_period_partitions_and_midnight(self, get, transform):
        index = pd.date_range('2026-09-30', periods=49, freq='h', tz='UTC')
        def payload(values):
            return {'hourly': {'time': index.strftime('%Y-%m-%dT%H:%M').tolist(),
                               **{key: [value] * len(index) for key, value in values.items()}}}
        get.side_effect = [payload({'wave_height': 1.2, 'wave_direction': 180,
                                    'wave_period': 14, 'wave_peak_period': None,
                                    'swell_wave_height': 1, 'swell_wave_direction': 170,
                                    'swell_wave_period': 14, 'secondary_swell_wave_height': .4,
                                    'secondary_swell_wave_direction': 90,
                                    'secondary_swell_wave_period': 8}),
                           payload({'wind_speed_10m': 18.52, 'wind_direction_10m': 270})]
        frame = fetch_gfs_forecast(start='2026-09-29T23:30Z')
        self.assertEqual(len(frame), 17)
        self.assertTrue((frame.peak_period_s == 14).all())
        self.assertTrue((frame.secondary_swell_period_s == 8).all())
        self.assertAlmostEqual(frame.wind_speed_kn.iloc[0], 10, places=5)
        for call in get.call_args_list:
            self.assertEqual(call.args[1]['end_date'], '2026-10-02')


if __name__ == '__main__':
    unittest.main()
