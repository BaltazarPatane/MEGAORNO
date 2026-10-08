"""Exporta una instantánea en otro proceso para no bloquear la recepción."""
from pathlib import Path
import os
import json
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from models import Sesion,exportar_csv
from reports import exportar_excel,exportar_pdf

def export_snapshot(source,destination,kind,selected_channels=None):
    session=Sesion.abrir(source);destination=Path(destination)
    fd,temp=tempfile.mkstemp(prefix='.megaorno-export-',suffix=destination.suffix,dir=destination.parent);os.close(fd)
    try:
        if kind=='CSV':exportar_csv(session,temp)
        elif kind=='EXCEL':exportar_excel(session,temp)
        elif kind=='PDF':
            import matplotlib
            matplotlib.use('Agg')
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from charts import render_chart
            fig=Figure(figsize=(12,6.8),layout='constrained');FigureCanvasAgg(fig);ax_t,ax_g=fig.subplots(2,1,sharex=True)
            if isinstance(selected_channels,str):selected_channels=json.loads(selected_channels)
            if selected_channels is None:selected_channels=list(session.registro.canales)
            if (not isinstance(selected_channels,list) or not selected_channels
                    or any(not isinstance(c,str) or c not in session.registro.canales for c in selected_channels)):
                raise ValueError('La selección de canales del PDF no es válida.')
            selected=[i for i,c in enumerate(session.registro.canales) if c in selected_channels]
            render_chart(fig,ax_t,ax_g,session,selected,mode='Ambas',show_ideal=True,show_band=True,full_program=True)
            fig.suptitle('Canales seleccionados en Curvas',fontsize=10,color='#647783')
            exportar_pdf(session,fig,temp)
        else:raise ValueError('Formato de exportación desconocido.')
        os.replace(temp,destination)
    finally:
        if os.path.exists(temp):os.unlink(temp)

if __name__=='__main__':
    try:export_snapshot(*sys.argv[1:])
    except Exception as e:
        print(str(e),file=sys.stderr);sys.exit(1)
