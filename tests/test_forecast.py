import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from surf_forecast import (ROOT, FEET_PER_METRE, lock_offshore_grid,
                           transform_waves, load_tide_events, tide_curve, TZ)
from forecast_plot import surf_height_band


class ScientificChecks(unittest.TestCase):
    def frame(self, directions, periods):
        return pd.DataFrame({'offshore_height_m': np.ones(len(directions)),
                             'wave_direction_deg': directions, 'peak_period_s': periods})

    def test_reference_cases_and_feet(self):
        result = transform_waves(self.frame([90, 180, 270, 0], [15, 10, 8, 4]))
        np.testing.assert_allclose(result.transfer_coefficient, [1.45689, .31555, 0, .19694])
        np.testing.assert_allclose(result.offshore_height_ft, [3.280839895] * 4)

    def test_half_up_and_north_wrap(self):
        result = transform_waves(self.frame([7.49, 7.5, 352.5, 360, -15], [10.49, 10.5, 12, 12, 12]))
        self.assertEqual(result.matrix_direction_deg.tolist(), [360, 15, 360, 360, 345])
        self.assertEqual(result.matrix_period_s.tolist(), [10, 11, 12, 12, 12])

    def test_legacy_skipped_columns_and_clipping(self):
        result = transform_waves(self.frame([90]*6, [7, 6, 3, 25, 22, 13]))
        self.assertEqual(result.matrix_column.tolist(), [13, 15, 17, 0, 1, 7])
        self.assertEqual(result.period_clipped.tolist(), [False, False, True, True, False, False])
        np.testing.assert_allclose(result.nearshore_height_ft, result.transfer_coefficient * FEET_PER_METRE)

    def test_invalid_wave_input(self):
        for period in [np.nan, 0, -1]:
            with self.assertRaises(ValueError):
                transform_waves(self.frame([90], [period]))

    def test_grid_lock_reused_without_reading_grib(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lock.json'
            path.write_text(json.dumps({'index': 123, 'latitude': -33.25}))
            self.assertEqual(lock_offshore_grid('nonexistent.grib2', path)['index'], 123)

    def test_tide_extrema_and_no_extrapolation(self):
        events = pd.DataFrame({'height_m': [0.3, 1.8, 0.4]},
                              index=pd.date_range('2026-09-29', periods=3, freq='6h', tz='UTC'))
        curve = tide_curve(events, events.index[0], events.index[-1])
        np.testing.assert_allclose(curve.loc[events.index], events.height_m)
        self.assertAlmostEqual(curve.iloc[18], 1.05)
        with self.assertRaises(ValueError):
            tide_curve(events, events.index[0], events.index[-1] + pd.Timedelta(hours=1))

    def test_bom_dst_and_table(self):
        events = load_tide_events()
        self.assertEqual(len(events), 38)
        local = events.index.tz_convert(TZ)
        self.assertEqual(local[22].utcoffset().total_seconds(), 36000)
        self.assertEqual(local[23].utcoffset().total_seconds(), 39600)
        self.assertAlmostEqual(events.iloc[23].height_m, 1.2)
        self.assertEqual(local[23].strftime('%Y-%m-%d %H:%M'), '2026-10-04 03:30')

    def test_surf_height_bands(self):
        self.assertEqual([surf_height_band(v) for v in [0, .99, 1, 5.99, 6, 11.99, 12]],
                         ['0-1ft', '0-1ft', '1-2ft', '5-6ft', '6-8ft', '10-12ft', '12ft+'])


if __name__ == '__main__':
    unittest.main()
