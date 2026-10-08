import sys
import unittest
from datetime import datetime,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import date2num
from models import Registro,Sesion
from charts import render_chart


class Charts(unittest.TestCase):
    def setUp(self):
        self.t=datetime(2026,10,5,11,30)
        self.fig=Figure(figsize=(10,6),layout='constrained');self.canvas=FigureCanvasAgg(self.fig)
        self.ax_t,self.ax_v=self.fig.subplots(2,1,sharex=True)

    def render(self,rows,**kwargs):
        r=Registro();r.agregar(rows);self.session=Sesion(registro=r)
        result=render_chart(self.fig,self.ax_t,self.ax_v,self.session,[0],**kwargs)
        self.canvas.draw();return result

    def test_single_measurement_stays_in_seconds(self):
        self.render([(self.t,'TC1',24)])
        lo,hi=self.ax_t.get_xlim()
        self.assertAlmostEqual((hi-lo)*86400,60,places=4)
        self.assertLess(lo,date2num(self.t));self.assertGreater(hi,date2num(self.t))
        self.assertTrue(self.ax_t.get_visible());self.assertFalse(self.ax_v.get_visible())
        self.assertLess(self.ax_t.get_ylim()[1]-self.ax_t.get_ylim()[0],2)
        self.assertTrue(any(':' in label.get_text() for label in self.ax_t.get_xticklabels()))

    def test_five_minutes_and_temperature_fit_actual_values(self):
        self.render([(self.t+timedelta(seconds=i*30),'TC1',v) for i,v in enumerate([23.3,23,22.6,22.6,22.3,23.9,29.9,30.5,27.9,26.6,25.5])])
        self.assertLess((self.ax_t.get_xlim()[1]-self.ax_t.get_xlim()[0])*1440,6)
        low,high=self.ax_t.get_ylim();self.assertLess(low,22.3);self.assertGreater(high,30.5);self.assertLess(high-low,11)

    def test_ideal_does_not_expand_x_unless_requested(self):
        rows=[(self.t,'TC1',24)]
        self.render(rows,show_ideal=True)
        self.assertLess((self.ax_t.get_xlim()[1]-self.ax_t.get_xlim()[0])*1440,2)
        self.render(rows,show_ideal=True,full_program=True)
        self.assertGreater((self.ax_t.get_xlim()[1]-self.ax_t.get_xlim()[0])*1440,440)
        self.assertLess((self.ax_t.get_xlim()[1]-self.ax_t.get_xlim()[0])*1440,500)

    def test_modes_share_correct_range_and_keep_rate_units(self):
        rows=[(self.t,'TC1',20),(self.t+timedelta(minutes=5),'TC1',30)]
        for mode in ['Velocidad','Ambas','Temperatura','Velocidad']:
            series=self.render(rows,mode=mode,unit='°C/h')
            self.assertEqual(self.ax_t.get_visible(),mode!='Velocidad');self.assertEqual(self.ax_v.get_visible(),mode!='Temperatura')
            self.assertEqual(self.ax_t.get_xlim(),self.ax_v.get_xlim())
            self.assertEqual(series[self.ax_v][0]['y'],[120.])

    def test_empty_invalid_and_first_rate(self):
        self.render([]);self.assertLess(self.ax_t.get_xlim()[1]-self.ax_t.get_xlim()[0],.01)
        self.render([(self.t,'TC1',None)]);self.assertTrue(any('no tienen temperaturas válidas' in text.get_text() for text in self.ax_t.texts))
        self.render([(self.t,'TC1',24)],mode='Velocidad');self.assertTrue(any('dos muestras' in text.get_text() for text in self.ax_v.texts))

    def test_rolling_window_and_invalid_gap(self):
        rows=[(self.t+timedelta(minutes=i),'TC1',20+i if i!=9 else None) for i in range(11)]
        result=self.render(rows,window_minutes=5)
        low,high=self.ax_t.get_xlim();self.assertGreater(low,date2num(self.t+timedelta(minutes=4)))
        self.assertLess((high-low)*1440,6)
        self.assertNotIn(date2num(self.t+timedelta(minutes=10)),result[self.ax_v][0]['x'])


if __name__=='__main__':unittest.main()
