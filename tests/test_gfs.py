"""Check GFS field mapping and the inclusive two-day forecast window."""
import unittest
from unittest.mock import patch

import pandas as pd

from gfs_forecast import fetch_gfs_forecast
from forecast_plot import surf_height_band


class GfsChecks(unittest.TestCase):
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
