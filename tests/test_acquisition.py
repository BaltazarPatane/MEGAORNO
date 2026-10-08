"""Pruebas sin hardware del ciclo WCF y la conservación de capturas."""
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition import AcquisitionController, ConnectionSettings
from models import Perfil, Sesion


class FakeBridge:
    def __init__(self, events):
        self.events = events
        self.request_id = 0
        self.running = False
        self.config = None
        self.stopped = False
        self.starts = 0

    def start(self, config, folder):
        self.request_id += 1
        self.running = True
        self.config = config
        self.starts += 1

    def stop(self):
        self.request_id += 1
        self.running = False
        self.stopped = True

    def emit(self, kind, data, request_id=None):
        self.events.put(dict(type=kind, data=data,
                             request_id=self.request_id if request_id is None else request_id))


def reading(timestamp='2026-09-29T08:00:00.123456', value='630', status='Valid', serial='R59022'):
    return dict(serial=serial, timestamp=timestamp, channels=[
        dict(position=1, unit='Celsius', status=status, value=value)])


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'captura.horno.json'
        self.settings = ConnectionSettings(vendor_dir=self.tmp.name)
        self.controller = AcquisitionController(Path(self.tmp.name) / 'state', FakeBridge)

    def connect(self, settings=None):
        self.controller.connect(settings or self.settings, self.path, Perfil())
        return self.controller.bridge

    def start_reading(self):
        bridge = self.connect()
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', reading())
        self.controller.drain()
        return bridge

    def test_single_operation_creates_capture_before_open_and_waits_for_valid_sample(self):
        saved_at_start = []
        controller = self.controller
        class InspectBridge(FakeBridge):
            def start(inner, config, folder):
                saved_at_start.append(Sesion.abrir(self.path))
                super().start(config, folder)
        controller.bridge_factory = InspectBridge
        bridge = self.connect()
        self.assertEqual(saved_at_start[0].registro.muestras, [])
        self.assertEqual(bridge.config['mode'], 'mt_poll')
        self.assertEqual(bridge.config['serial'], '')
        bridge.emit('transport_open', self.settings.endpoint)
        bridge.emit('mt_devices', ['R59022'])
        events = controller.drain()
        self.assertNotIn('ready', [e['type'] for e in events])
        bridge.emit('mt_reading', reading())
        events = controller.drain()
        self.assertEqual([e['type'] for e in events].count('ready'), 1)
        self.assertEqual(bridge.starts, 1)
        self.assertEqual(controller.state, 'receiving')
        self.assertEqual(Sesion.abrir(self.path).registro.serie, 'R59022')

    def test_invalid_first_reading_saved_without_unlocking_login(self):
        bridge = self.connect()
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', reading(status='SensorError'))
        events = self.controller.drain()
        self.assertNotIn('ready', [e['type'] for e in events])
        self.assertEqual(self.controller.state, 'waiting')
        self.assertIsNone(next(iter(Sesion.abrir(self.path).registro.muestras[0][1].values())))
        bridge.emit('mt_reading', reading(timestamp='2026-09-29T08:05:00'))
        events = self.controller.drain()
        self.assertIn('ready', [e['type'] for e in events])
        self.assertIsNone(self.controller.session.registro.velocidades[-1]['R59022 / Posición WCF 1'])

    def test_duplicates_are_deduplicated_and_fractional_timestamp_retained(self):
        bridge = self.start_reading()
        bridge.emit('mt_reading', reading())
        bridge.emit('mt_reading', reading())
        events = self.controller.drain()
        self.assertEqual([e['data']['changed'] for e in events if e['type'] == 'sample'], [0, 0])
        record = Sesion.abrir(self.path).registro
        self.assertEqual(len(record.muestras), 1)
        self.assertEqual(record.muestras[0][0].microsecond, 123456)
        lines = Path(str(self.path) + '.wcf.jsonl').read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['madgetech']['timestamp'], reading()['timestamp'])

    def test_out_of_order_samples_and_invalids_use_measurement_time(self):
        bridge = self.start_reading()
        for payload in [reading('2026-09-29T08:10:00', '650'),
                        reading('2026-09-29T08:05:00', '640'),
                        reading('2026-09-29T08:07:00', status='SensorError')]:
            bridge.emit('mt_reading', payload)
        self.controller.drain()
        record = self.controller.session.registro
        self.assertEqual([dt.minute for dt, _ in record.muestras], [0, 5, 7, 10])
        self.assertIsNone(record.velocidades[-1][record.canales[0]])

    def test_multiple_devices_requires_selection_without_reading(self):
        bridge = self.connect()
        bridge.emit('mt_devices', ['R1', 'R2'])
        events = self.controller.drain()
        self.assertIn(dict(type='selection_required', data=['R1', 'R2']), events)
        self.assertEqual(self.controller.state, 'selection_required')
        self.assertTrue(bridge.stopped)
        self.assertFalse(self.controller.running)
        self.controller.connect(replace(self.settings, serial='R2'), self.path, Perfil())
        bridge = self.controller.bridge
        bridge.emit('mt_devices', ['R1', 'R2'])
        bridge.emit('mt_reading', reading(serial='R2'))
        self.assertIn('ready', [e['type'] for e in self.controller.drain()])

    def test_no_device_is_error_and_keeps_empty_capture(self):
        bridge = self.connect()
        bridge.emit('mt_devices', [])
        self.controller.drain()
        self.assertEqual(self.controller.state, 'error')
        self.assertTrue(bridge.stopped)
        self.assertTrue(self.path.exists())

    def test_mismatched_serial_stops_before_inserting_reading(self):
        bridge = self.start_reading()
        bridge.emit('mt_reading', reading(serial='UNEXPECTED'))
        events = self.controller.drain()
        self.assertEqual(self.controller.state, 'error')
        self.assertIn('error', [e['type'] for e in events])
        self.assertEqual(len(self.controller.session.registro.muestras), 1)

    def test_error_and_disconnect_preserve_captured_data(self):
        bridge = self.start_reading()
        session = self.controller.session
        bridge.emit('fault', 'CommunicationLostException')
        self.controller.drain()
        self.assertTrue(bridge.stopped)
        self.assertEqual(self.controller.state, 'error')
        self.controller.disconnect()
        self.assertIs(self.controller.session, session)
        self.assertEqual(self.controller.session_path, self.path)
        self.assertEqual(len(Sesion.abrir(self.path).registro.muestras), 1)

    def test_late_request_ids_and_prior_bridge_events_are_discarded(self):
        first = self.connect()
        first_id = first.request_id
        self.controller.disconnect()
        self.controller.connect(self.settings, self.path)
        second = self.controller.bridge
        self.assertEqual(second.request_id, first_id)
        first.emit('error', 'Late bridge error', request_id=first_id)
        second.emit('error', 'Wrong request id', request_id=second.request_id + 1)
        second.emit('mt_devices', ['R59022'])
        second.emit('mt_reading', reading())
        events = self.controller.drain()
        self.assertNotIn('error', [e['type'] for e in events])
        self.assertEqual(self.controller.state, 'receiving')

    def test_search_has_no_capture_and_finishes_cleanly(self):
        self.controller.search(self.settings)
        bridge = self.controller.bridge
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('finished', 'mt_list')
        events = self.controller.drain()
        self.assertIn(dict(type='devices', data=['R59022']), events)
        self.assertIsNone(self.controller.session)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.controller.state, 'disconnected')

    def test_unexpected_process_exit_keeps_data_and_reports_error(self):
        bridge = self.start_reading()
        bridge.emit('finished', 'mt_poll')
        events = self.controller.drain()
        self.assertIn('error', [e['type'] for e in events])
        self.assertEqual(self.controller.state, 'error')
        self.assertEqual(len(self.controller.session.registro.muestras), 1)

    def test_save_failure_stops_and_retains_new_sample_in_memory(self):
        bridge = self.start_reading()
        bridge.emit('mt_reading', reading('2026-09-29T08:05:00', '640'))
        with patch.object(self.controller.session, 'guardar', side_effect=OSError('Disk full')):
            events = self.controller.drain()
        self.assertEqual(self.controller.state, 'error')
        self.assertTrue(bridge.stopped)
        self.assertEqual(len(self.controller.session.registro.muestras), 2)
        self.assertEqual(len(Sesion.abrir(self.path).registro.muestras), 1)
        self.assertIn('error', [e['type'] for e in events])

    def test_raw_capture_failure_stops_and_retains_new_sample(self):
        bridge = self.start_reading()
        bridge.emit('mt_reading', reading('2026-09-29T08:05:00', '640'))
        with patch.object(self.controller, '_capture_raw', side_effect=OSError('Disk full')):
            self.controller.drain()
        self.assertEqual(self.controller.state, 'error')
        self.assertTrue(bridge.stopped)
        self.assertEqual(len(self.controller.session.registro.muestras), 2)

    def test_initial_save_failure_prevents_start(self):
        with patch.object(Sesion, 'guardar', side_effect=OSError('Read-only volume')):
            with self.assertRaises(OSError):
                self.connect()
        self.assertIsNone(self.controller.bridge)
        self.assertFalse(self.controller.running)

    def test_first_sample_is_not_ready_if_its_autosave_fails(self):
        bridge = self.connect()
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', reading())
        with patch.object(self.controller.session, 'guardar', side_effect=OSError('Disk full')):
            events = self.controller.drain()
        self.assertNotIn('ready', [e['type'] for e in events])
        self.assertEqual(self.controller.state, 'error')
        self.assertEqual(len(self.controller.session.registro.muestras), 1)

    def test_confirmed_unit_and_status_are_used_for_readings(self):
        settings = replace(self.settings, unit='°F', valid_status='ManufacturerValid')
        bridge = self.connect(settings)
        payload = reading(value='212', status='ManufacturerValid')
        payload['channels'][0]['unit'] = 'ManufacturerTemperature'
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', payload)
        events = self.controller.drain()
        self.assertIn('ready', [e['type'] for e in events])
        self.assertEqual(next(iter(self.controller.session.registro.muestras[0][1].values())), 100.)

    def test_incomplete_or_malformed_reading_cannot_unlock_login(self):
        bridge = self.connect()
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', dict(serial='R59022', timestamp='not a measurement date', channels=[]))
        events = self.controller.drain()
        self.assertNotIn('ready', [e['type'] for e in events])
        self.assertEqual(self.controller.state, 'error')
        self.assertEqual(self.controller.session.registro.muestras, [])

    def test_cannot_overwrite_a_capture_or_reconnect_while_running(self):
        self.start_reading()
        with self.assertRaises(ValueError):
            self.controller.connect(self.settings, self.path)
        self.controller.disconnect()
        with self.assertRaises(FileExistsError):
            self.controller.connect(self.settings, self.path)

    def test_credentials_stay_out_of_files_repr_and_log_events(self):
        settings = replace(self.settings, authenticate=True, username='PRIVATE_OPERATOR', password='SUPER_SECRET')
        bridge = self.connect(settings)
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', reading())
        bridge.emit('log', 'PRIVATE_OPERATOR accidentally logged SUPER_SECRET')
        bridge.emit('error', 'SUPER_SECRET failed for PRIVATE_OPERATOR')
        events = self.controller.drain()
        text = repr(settings) + str(events)
        for path in Path(self.tmp.name).rglob('*'):
            if path.is_file():
                text += path.read_text()
        self.assertNotIn(settings.username, text)
        self.assertNotIn(settings.password, text)
        self.assertEqual(bridge.config['password'], settings.password)

    def test_disabled_authentication_never_sends_stale_credentials(self):
        settings = replace(self.settings, username='operator', password='stale')
        bridge = self.connect(settings)
        self.assertEqual(bridge.config['username'], '')
        self.assertEqual(bridge.config['password'], '')

    def test_settings_reject_invalid_poll_and_nonlocal_endpoint(self):
        for poll in (0, 3601, 1.5, True, '5'):
            with self.subTest(poll=poll), self.assertRaises(ValueError):
                replace(self.settings, poll_seconds=poll).bridge_config('mt_poll')
        for endpoint in ('https://localhost/MT4Data', 'net.pipe://other-host/MT4Data',
                         'net.pipe://user:secret@localhost/MT4Data', 'net.pipe://localhost/MT4Data?secret=abc'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                replace(self.settings, endpoint=endpoint).bridge_config('mt_poll')


if __name__ == '__main__':
    unittest.main()
