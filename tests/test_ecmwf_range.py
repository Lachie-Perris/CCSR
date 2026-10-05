import unittest
import pandas as pd
from surf_forecast import forecast_steps, resample_forecast


class ExtendedRangeChecks(unittest.TestCase):
    def test_transition_and_bracketing(self):
        self.assertEqual(forecast_steps(141, 159, 0), [141, 144, 150, 156, 162])
        self.assertEqual(forecast_steps(153, 201, 12), list(range(150, 205, 6)))
        with self.assertRaises(ValueError):
            forecast_steps(141, 159, 6)
        with self.assertRaises(ValueError):
            forecast_steps(350, 363, 0)

    def test_interpolation_wraps_north(self):
        native = pd.DataFrame({'wave_direction_deg': [350., 10.],
                               'offshore_height_m': [2., 4.]},
                              index=pd.date_range('2026-10-10', periods=2, freq='6h', tz='UTC'))
        result = resample_forecast(native, pd.date_range(native.index[0], periods=3, freq='3h'))
        self.assertAlmostEqual(result.wave_direction_deg.iloc[1] % 360, 0)
        self.assertEqual(result.offshore_height_m.tolist(), [2, 3, 4])
        with self.assertRaises(ValueError):
            resample_forecast(native, pd.date_range(native.index[0], periods=4, freq='3h'))
