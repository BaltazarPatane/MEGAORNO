import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live import decodificar_madgetech
from models import Registro


class MadgeTech(unittest.TestCase):
    def payload(self):
        return dict(serial='R59022',timestamp='2026-09-29T08:00:00',channels=[
            dict(position=1,unit='Celsius',status='Valid',value='630'),
            dict(position=2,unit='Fahrenheit',status='Valid',value='1166'),
            dict(position=3,unit='Kelvin',status='Valid',value='903.15')])

    def test_celsius_fahrenheit_kelvin_positions(self):
        rows,errors=decodificar_madgetech(self.payload());self.assertFalse(errors)
        self.assertEqual([v for _,_,v in rows],[630.,630.,630.])
        self.assertEqual([c for _,c,_ in rows],[f'R59022 / Posición WCF {i}' for i in range(1,4)])

    def test_invalid_status_unit_nonfinite_never_become_temperature(self):
        p=self.payload();p['channels'][0]['status']='SensorError';p['channels'][1]['unit']='Volt';p['channels'][2]['value']='NaN'
        rows,errors=decodificar_madgetech(p);self.assertEqual([v for _,_,v in rows],[None]*3);self.assertEqual(len(errors),3)
        p['channels'][0]['status']='0';rows,_=decodificar_madgetech(p);self.assertIsNone(rows[0][2])

    def test_confirmed_manual_interpretation(self):
        p=self.payload();p['channels']=[dict(position=4,unit='UnknownTemperatureEnum',status='ManufacturerSpecificValid',value='212')]
        rows,errors=decodificar_madgetech(p);self.assertIsNone(rows[0][2]);self.assertTrue(errors)
        rows,errors=decodificar_madgetech(p,unit='°F',valid_status='ManufacturerSpecificValid');self.assertEqual(rows[0][2],100);self.assertFalse(errors)

    def test_repeated_latest_and_invalid_samples_break_rate(self):
        p=self.payload();p['channels']=p['channels'][:1];r=Registro();rows,_=decodificar_madgetech(p)
        self.assertEqual(r.agregar(rows),1);self.assertEqual(r.agregar(rows),0)
        p['timestamp']='2026-09-29T08:05:00';p['channels'][0]['status']='SensorError';rows,_=decodificar_madgetech(p)
        self.assertEqual(r.agregar(rows),1);self.assertEqual(r.agregar(rows),0)
        p['timestamp']='2026-09-29T08:10:00';p['channels'][0].update(status='Valid',value='640');rows,_=decodificar_madgetech(p);r.agregar(rows)
        channel=r.canales[0];self.assertIsNone(r.muestras[1][1][channel]);self.assertIsNone(r.gradientes[2][channel])
        p['timestamp']='2026-09-29T08:15:01';p['channels'][0]['value']='650';rows,_=decodificar_madgetech(p);r.agregar(rows)
        self.assertAlmostEqual(r.gradientes[-1][channel]*60,10*3600/301)

    def test_malformed_and_empty(self):
        p=self.payload();p['channels']=[];self.assertEqual(decodificar_madgetech(p),([],[]))
        for change in [dict(serial=''),dict(timestamp='0001-01-01'),dict(channels=None)]:
            malformed=self.payload();malformed.update(change)
            with self.assertRaises(ValueError):decodificar_madgetech(malformed)
        p=self.payload();p['channels'][1]['position']=1
        with self.assertRaises(ValueError):decodificar_madgetech(p)

    def test_timestamp_zone_converted_to_pc_local(self):
        p=self.payload();p['timestamp']='2026-09-29T08:00:00-03:00';rows,_=decodificar_madgetech(p)
        expected=datetime.fromisoformat(p['timestamp']).astimezone().replace(tzinfo=None)
        self.assertEqual(rows[0][0],expected)


if __name__=='__main__':unittest.main()
