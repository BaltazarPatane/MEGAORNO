"""Navigation must never invent readings or lose the operator's manual view."""
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from matplotlib.dates import date2num
from PySide6.QtWidgets import QApplication
from models import Registro, Sesion
from ui.chart_widget import ChartWidget


class ChartNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.origin = datetime(2026, 10, 6, 12)
        register = Registro()
        register.agregar([
            (self.origin + timedelta(minutes=i), "TC1", 20 + 2 * i)
            for i in range(30)
        ])
        self.session = Sesion(registro=register)
        self.widget = ChartWidget()
        self.widget.resize(1000, 600)
        self.widget.set_session(self.session)
        self.widget.canvas.draw()

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()

    def event(self, data_x=None, data_y=35, **kwargs):
        ax = self.widget.ax_t
        if data_x is None:
            data_x = date2num(self.origin + timedelta(minutes=10))
        px, py = ax.transData.transform((data_x, data_y))
        params = dict(inaxes=ax, xdata=data_x, ydata=data_y, x=px, y=py,
                      key=None, button=1, dblclick=False, step=1)
        params.update(kwargs)
        return SimpleNamespace(**params)

    def test_wheel_is_anchored_to_pointer_and_pauses_follow(self):
        chart = self.widget
        changes = []
        chart.view_changed.connect(changes.append)
        event = self.event()
        low, high = chart.ax_t.get_xlim()
        old_y = chart.ax_t.get_ylim()
        fraction = (event.xdata - low) / (high - low)
        chart._on_scroll(event)
        new_low, new_high = chart.ax_t.get_xlim()
        self.assertAlmostEqual(new_high - new_low, (high - low) / 1.25)
        self.assertAlmostEqual((event.xdata - new_low) / (new_high - new_low), fraction)
        self.assertEqual(chart.ax_t.get_ylim(), old_y)
        self.assertFalse(chart.follow)
        self.assertEqual(changes, [False])

    def test_incoming_samples_preserve_manual_view_then_follow_resumes(self):
        chart = self.widget
        chart._on_scroll(self.event(key="control"))
        xlim, ylim = chart.ax_t.get_xlim(), chart.ax_t.get_ylim()
        new_time = self.origin + timedelta(minutes=40)
        self.session.registro.agregar([(new_time, "TC1", 110)])
        chart.refresh()
        self.assertEqual(chart.ax_t.get_xlim(), xlim)
        self.assertEqual(chart.ax_t.get_ylim(), ylim)
        chart.set_follow(True)
        self.assertTrue(chart.follow)
        self.assertGreater(chart.ax_t.get_xlim()[1], date2num(new_time))
        self.assertGreater(chart.ax_t.get_ylim()[1], 110)

    def test_drag_pans_shared_time_without_changing_vertical_scale(self):
        chart = self.widget
        chart.set_options(mode="Ambas")
        chart.canvas.draw()
        event = self.event()
        xlim, ylim = chart.ax_t.get_xlim(), chart.ax_t.get_ylim()
        chart._on_press(event)
        chart._on_motion(self.event(data_x=event.xdata, x=event.x + 60, y=event.y + 20))
        new_xlim = chart.ax_t.get_xlim()
        self.assertLess(new_xlim[0], xlim[0])
        self.assertAlmostEqual(new_xlim[1] - new_xlim[0], xlim[1] - xlim[0])
        self.assertEqual(chart.ax_t.get_xlim(), chart.ax_v.get_xlim())
        self.assertEqual(chart.ax_t.get_ylim(), ylim)
        self.assertFalse(chart.follow)
        chart._on_release(event)
        self.assertIsNone(chart._drag)

    def test_double_click_fits_and_time_window_follows_latest(self):
        chart = self.widget
        chart._on_scroll(self.event())
        chart._on_press(self.event(dblclick=True))
        self.assertTrue(chart.follow)
        chart.set_options(window_minutes=5)
        low, high = chart.ax_t.get_xlim()
        self.assertGreater(low, date2num(self.origin + timedelta(minutes=23)))
        self.assertLess((high - low) * 1440, 6)

    def test_cursor_reports_exact_sample_and_skips_invalid_readings(self):
        chart = self.widget
        self.session.registro.agregar([(self.origin + timedelta(minutes=10), "TC1", None)])
        chart.refresh()
        chart.canvas.draw()
        # The pointer sits between data points; the value must be from a sample.
        event = self.event(data_x=date2num(self.origin + timedelta(minutes=10, seconds=10)), data_y=40.3)
        point = chart._nearest_sample(event)
        self.assertIsNotNone(point)
        _, x, y = point
        recorded = {(date2num(t), values["TC1"]) for t, values in self.session.registro.muestras
                    if values["TC1"] is not None}
        self.assertIn((x, y), recorded)
        chart._on_motion(event)
        self.assertIn("TC1", chart._cursor_label)
        self.assertNotIn("40.3", chart._cursor_label)

    def test_unit_change_keeps_manual_time_and_recomputes_rate_scale(self):
        chart = self.widget
        chart.set_options(mode="Velocidad", unit="°C/h")
        chart.canvas.draw()
        chart.set_follow(False)
        chart.ax_v.set_xlim(date2num(self.origin + timedelta(minutes=5)),
                            date2num(self.origin + timedelta(minutes=15)))
        old_xlim = chart.ax_v.get_xlim()
        chart.set_options(unit="°C/min")
        self.assertEqual(chart.ax_v.get_xlim(), old_xlim)
        self.assertEqual(chart._series[chart.ax_v][0]["y"], [2.] * 29)
        self.assertLess(chart.ax_v.get_ylim()[1], 3)

    def test_invalid_options_do_not_partially_change_configuration(self):
        original = self.widget.options
        with self.assertRaises(ValueError):
            self.widget.set_options(unit="kelvin", mode="Ambas")
        self.assertEqual(self.widget.options, original)


if __name__ == "__main__":
    unittest.main()
