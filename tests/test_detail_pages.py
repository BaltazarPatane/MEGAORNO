"""Regression checks for editable recipes and the full measurement/annotation UI."""
import os
import sys
import unittest
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from models import Perfil, Registro, Sesion
from ui.detail_pages import (ProfilePage, StatisticsPage,
                             build_manual_event, profile_from_fields)
from ui.table_models import MeasurementsModel


class DetailPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.start = datetime(2026, 10, 6, 12, 0, 0)

    def test_profile_accepts_decimal_comma_and_rejects_nonfinite_and_invalid_band(self):
        values = asdict(Perfil())
        values['hueco_max'] = '7,25'
        self.assertEqual(profile_from_fields(values).hueco_max, 7.25)
        for invalid in ('nan', 'inf', '0', '-1'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                profile_from_fields({**values, 'subida': invalid})
        with self.assertRaises(ValueError):
            profile_from_fields({**values, 'inferior': '631'})

    def test_profile_emits_validated_object_without_mutating_session(self):
        session = Sesion(perfil=Perfil(bajada=123.12345678912345))
        page = ProfilePage(session)
        emitted = []
        page.profile_applied.connect(emitted.append)
        page.fields['subida'].setText('240,5')
        page.refresh()  # Background acquisition cannot erase an unfinished edit.
        self.assertEqual(page.fields['subida'].text(), '240,5')
        page.apply_profile()
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].subida, 240.5)
        self.assertEqual(emitted[0].bajada, session.perfil.bajada)
        self.assertEqual(session.perfil.subida, 150)
        page.close()

    def test_annotation_snapshot_preserves_invalid_and_ignores_future_and_stale(self):
        s = Sesion(registro=Registro(canales=['A', 'B', 'C'], muestras=[
            (self.start, {'A': 25, 'B': 27, 'C': 29}),
            (self.start + timedelta(minutes=7), {'A': None}),
            (self.start + timedelta(minutes=8), {'B': 40}),
            (self.start + timedelta(minutes=10), {'A': 100, 'B': 100, 'C': 100}),
        ]))
        event = build_manual_event(s, self.start + timedelta(minutes=9), ['0', '100', '', '12,5', None, '50'], ' Ana ', ' Ajuste ')
        self.assertEqual(event['temperaturas'], {'A': None, 'B': 40})
        self.assertEqual(event['zonas'], [0, 100, None, 12.5, None, 50])
        self.assertEqual(event['operador'], 'Ana')
        self.assertEqual(event['nota'], 'Ajuste')
        self.assertEqual(s.controladores, [])
        at_reading = build_manual_event(s, self.start + timedelta(minutes=10), [None] * 6)
        self.assertEqual(at_reading['temperaturas'], {'A': 100, 'B': 100, 'C': 100})

    def test_annotation_requires_samples_and_six_finite_zone_percentages(self):
        with self.assertRaises(ValueError):
            build_manual_event(Sesion(), self.start, [None] * 6)
        session = Sesion(registro=Registro(canales=['A'], muestras=[(self.start, {'A': 20})]))
        for bad_zones in ([0] * 5, ['nan'] * 6, [101] * 6, [-1] * 6):
            with self.subTest(zones=bad_zones), self.assertRaises(ValueError):
                build_manual_event(session, self.start, bad_zones)

    def test_measurement_model_keeps_every_row_and_actual_intervals(self):
        count = 25001
        registro = Registro(canales=['A'], muestras=[
            (self.start + timedelta(seconds=15 * i), {'A': 20.0 + i / 100})
            for i in range(count)
        ])
        registro.recalcular()
        model = MeasurementsModel(Sesion(registro=registro))
        self.assertEqual(model.rowCount(), count)
        self.assertEqual(model.columnCount(), 5)
        self.assertEqual(model.data(model.index(count - 1, 3)), '270.000')
        self.assertEqual(model.data(model.index(count - 1, 4)), '2.400')
        self.assertEqual(model.data(model.index(0, 4)), '—')
        model.set_unit('°C/min')
        self.assertEqual(model.data(model.index(count - 1, 4)), '0.040')
        self.assertIs(model.session.registro, registro)

    def test_statistics_include_last_valid_date_and_both_extreme_dates(self):
        r = Registro(canales=['A'], muestras=[
            (self.start, {'A': 10}),
            (self.start + timedelta(minutes=1), {'A': 30}),
            (self.start + timedelta(minutes=2), {'A': 20}),
            (self.start + timedelta(minutes=3), {'A': None}),
        ])
        page = StatisticsPage(Sesion(registro=r))
        row = page.model.rows[0]
        self.assertEqual(row[1:7], [20, self.start + timedelta(minutes=2), 10, self.start, 30, self.start + timedelta(minutes=1)])
        self.assertEqual(row[7], 1200)
        self.assertEqual(row[9], -600)
        page.unit_combo.setCurrentText('°C/min')
        self.assertEqual(page.model.rows[0][7], 20)
        self.assertEqual(page.model.rows[0][9], -10)
        page.close()


if __name__ == '__main__':
    unittest.main()
