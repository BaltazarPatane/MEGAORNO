"""Exportación de resultados sin depender de Microsoft Excel."""
from dataclasses import asdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from openpyxl import Workbook
from openpyxl.chart import Reference,ScatterChart,Series
from openpyxl.styles import Font,PatternFill,Alignment
from models import fecha_local
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,Image,PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def exportar_excel(sesion,ruta):
    summary,alerts=sesion.analisis();r,p=sesion.registro,sesion.perfil;w=Workbook();w.remove(w.active)
    def sheet(name,headers,rows):
        s=w.create_sheet(name);s.append(headers)
        for cell in s[1]:
            if isinstance(cell.value,str):cell.data_type='s'
        for row in rows:
            s.append(row)
            for cell in s[s.max_row]:
                if isinstance(cell.value,str):cell.data_type='s'
                elif isinstance(cell.value,datetime):cell.number_format='dd/mm/yyyy hh:mm:ss'
                elif isinstance(cell.value,(float,int)):cell.number_format='0.00'
        s.freeze_panes='A2';s.auto_filter.ref=s.dimensions;s.row_dimensions[1].height=34
        for c in s[1]:c.fill=PatternFill('solid',fgColor='17394C');c.font=Font(color='FFFFFF',bold=True);c.alignment=Alignment(wrap_text=True,vertical='center')
        for col in s.columns:s.column_dimensions[col[0].column_letter].width=min(48,max(18,max(len(str(c.value or '')) for c in col[:100])+2))
        for row in s.iter_rows(min_row=2):
            if row[0].row%2==0:
                for c in row:c.fill=PatternFill('solid',fgColor='EFF4F7')
        return s
    labels=dict(inicio='Temperatura inicial °C',objetivo='Objetivo °C',final='Temperatura final °C',subida='Ascenso °C/h',bajada='Descenso (magnitud) °C/h',mantenimiento='Mantenimiento min',inferior='Banda inferior °C',superior='Banda superior °C',desfase='Inicio desde primera muestra min',hueco_max='Límite de huecos min')
    sheet('Receta',['Parámetro','Valor'],[['Tratamiento',sesion.titulo],['Modo',sesion.modo],['Archivo',r.origen],['Serie',r.serie]]+[[labels[k],v] for k,v in asdict(p).items()]+[['Método','Diferencia de temperatura / intervalo real por canal'],['Tramo en banda','Extremos medidos consecutivos en banda; sin interpolar cruces'],['Avisos','Comparación con la receta; no es una aprobación del tratamiento']])
    data=[]
    for i,(dt,vals) in enumerate(r.muestras):
        minutes=(dt-r.muestras[0][0]).total_seconds()/60;ideal,phase=p.punto(minutes);row=[dt,minutes,ideal,phase]
        for c in r.canales:
            rate=r.velocidades[i].get(c);row += [vals.get(c),rate*60 if rate is not None else None,rate]
        data.append(row)
    s=sheet('Datos',['Fecha y hora','Minutos','Ideal °C','Etapa']+[sesion.nombre(c)+' '+u for c in r.canales for u in ('°C','°C/h','°C/min')],data)
    if data:
        # Each channel has its own timestamps. The hidden drawing table contains
        # explicit breaks for invalid readings/long gaps, while Datos preserves
        # every original measurement unchanged.
        plotted=[('Ideal °C',[(row[1],row[2]) for row in data])]
        origin=r.muestras[0][0]
        for channel in r.canales:
            points=[];previous=None
            for dt,values in r.muestras:
                if channel not in values:continue
                minute=(dt-origin).total_seconds()/60
                if previous is not None and (dt-previous).total_seconds()/60>p.hueco_max:
                    points.append((minute,None))
                points.append((minute,values[channel]));previous=dt
            plotted.append((sesion.nombre(channel)+' °C',points))
        drawing=[]
        for index in range(max(len(points) for _,points in plotted)):
            drawing.append([value for _,points in plotted for value in (points[index] if index<len(points) else (None,None))])
        source=sheet('Trazado',[title for name,_ in plotted for title in ('Minutos',name)],drawing)
        source.sheet_state='hidden'
        chart=ScatterChart();chart.title='Temperaturas e ideal';chart.x_axis.title='Minutos desde primera muestra';chart.y_axis.title='°C';chart.display_blanks='gap'
        chart.visible_cells_only=False
        for index,(_,points) in enumerate(plotted):
            if not points:continue
            x=Reference(source,min_col=2*index+1,min_row=2,max_row=len(points)+1)
            series=Series(Reference(source,min_col=2*index+2,min_row=1,max_row=len(points)+1),x,title_from_data=True)
            if index==0:series.graphicalProperties.line.prstDash='dash';series.graphicalProperties.line.solidFill='243D4A'
            chart.series.append(series)
        chart.width=29;chart.height=14;w.create_sheet('Curvas').add_chart(chart,'A1')
    rows=[]
    for x in summary:
        if not x['n']:rows.append([sesion.nombre(x['canal']),0]+[None]*11);continue
        rows.append([sesion.nombre(x['canal']),x['n'],x['ultima'],x['tultima'],x['maximo'],x['tmax'],x['minimo'],x['tmin'],x['subida']*60 if x['subida'] is not None else None,x['tsubida'],x['bajada']*60 if x['bajada'] is not None else None,x['tbajada'],x['racha']])
    sheet('Estadísticas',['Canal','Lecturas','Última °C','Fecha última','Máxima °C','Fecha máxima','Mínima °C','Fecha mínima','Mayor subida °C/h','Fecha subida','Mayor descenso °C/h','Fecha descenso','Tramo en banda min'],rows)
    sheet('Controladores',['Fecha y hora','Programada °C','Operador']+[f'Zona {i} %' for i in range(1,7)]+[sesion.nombre(c)+' °C' for c in r.canales]+['Incidencia'],[[fecha_local(e['fecha']),e['ideal'],e['operador']]+e['zonas']+[e['temperaturas'].get(c) for c in r.canales]+[e['nota']] for e in sesion.controladores])
    sheet('Avisos',['Fecha y hora','Canal','Observación','Detalle'],[[dt,sesion.nombre(c),kind,detail] for dt,c,kind,detail in alerts]);sheet('Importación',['Observación'],[[note] for note in r.notas] or [['Sin observaciones de importación.']]);w.save(ruta)


def exportar_pdf(sesion,figura,ruta):
    fonts=Path(reportlab.__file__).resolve().parent/'fonts'
    for name,filename in [('HornoSans','Vera.ttf'),('HornoSans-Bold','VeraBd.ttf'),('HornoSans-Italic','VeraIt.ttf'),('HornoSans-BoldItalic','VeraBI.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(fonts/filename)))
    pdfmetrics.registerFontFamily('HornoSans',normal='HornoSans',bold='HornoSans-Bold',italic='HornoSans-Italic',boldItalic='HornoSans-BoldItalic')
    styles=getSampleStyleSheet()
    for style in styles.byName.values():style.fontName='HornoSans-Bold' if 'Heading' in style.name else 'HornoSans'
    styles.add(ParagraphStyle(name='Cell',fontName='HornoSans',fontSize=8,leading=11))
    def par(t):return Paragraph(escape(str(t)),styles['Cell'])
    def table(rows,widths):
        tb=Table([[par(c) for c in row] for row in rows],colWidths=widths,repeatRows=1)
        tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6edf2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,-1),.3,colors.lightgrey)]));return tb
    summary,alerts=sesion.analisis();r,p=sesion.registro,sesion.perfil
    def n(x):return 'Sin dato' if x is None else f'{x:.2f}'
    doc=SimpleDocTemplate(str(ruta),pagesize=landscape(A4),leftMargin=35,rightMargin=35,topMargin=32,bottomMargin=32,title=sesion.titulo,author='Visor de horno')
    rows=[Paragraph(escape(sesion.titulo),styles['Title']),par(f'Modo: {sesion.modo} | Fuente: {r.origen} | Serie: {r.serie} | Muestras: {len(r.muestras)}'),
          par(f'Programa: {p.inicio:g} a {p.objetivo:g} °C, +{p.subida:g} °C/h; mantener {p.mantenimiento:g} min; bajar a {p.final:g} °C, -{p.bajada:g} °C/h. Banda {p.inferior:g}-{p.superior:g} °C.'),
          par(f'Inicio del programa: {p.desfase:g} min desde la primera muestra.'),
          par(f'La velocidad usa el intervalo real. Se omite con datos faltantes o huecos mayores a {p.hueco_max:g} min.'),Spacer(1,8)]
    img=BytesIO();figura.savefig(img,format='png',dpi=135,bbox_inches='tight');img.seek(0)
    from PIL import Image as PILImage
    wh=PILImage.open(img).size;img.seek(0);width=min(750,300*wh[0]/wh[1]);height=width*wh[1]/wh[0]
    rows += [Image(img,width=width,height=height),PageBreak(),Paragraph('Resumen de canales',styles['Heading1'])]
    last=[['Canal','Lecturas válidas','Última válida °C','Fecha de última válida']]
    for item in summary:
        last.append([sesion.nombre(item['canal']),item['n'],n(item.get('ultima')),item['tultima'].strftime('%d/%m/%Y %H:%M:%S') if item['n'] else 'Sin datos'])
    rows += [table(last,[270,100,120,280]),Spacer(1,12)]
    data=[['Canal','Máxima °C / fecha','Mínima °C / fecha','Mayor subida °C/h / fecha','Mayor descenso °C/h / fecha','Mayor tramo en banda (min)']]
    def dated(value,dt):return n(value)+((' / '+dt.strftime('%d/%m/%Y %H:%M:%S')) if dt else '')
    for s in summary:
        if not s['n']:data.append([sesion.nombre(s['canal'])]+['Sin datos']*5);continue
        data.append([sesion.nombre(s['canal']),dated(s['maximo'],s['tmax']),dated(s['minimo'],s['tmin']),dated(s['subida']*60 if s['subida'] is not None else None,s['tsubida']),dated(s['bajada']*60 if s['bajada'] is not None else None,s['tbajada']),n(s['racha'])])
    rows += [table(data,[170,140,125,115,115,105]),Spacer(1,8),par('Tramo en banda: duración entre muestras consecutivas válidas, ambas en banda; sin interpolar cruces. Los avisos comparan con la receta y no constituyen una aprobación del tratamiento.')]
    if sesion.controladores:
        rows += [Spacer(1,12),Paragraph('Registro manual de controladores',styles['Heading1'])];data=[['Fecha','Operador','Ideal °C','Zonas 1 a 6 (%)','Lecturas °C','Incidencia']]
        for e in sesion.controladores:data.append([e['fecha'],e['operador'],n(e['ideal']),', '.join('—' if v is None else str(v) for v in e['zonas']),'; '.join(sesion.nombre(c)+': '+n(v) for c,v in e['temperaturas'].items()),e['nota']])
        rows.append(table(data,[112,75,55,125,170,233]))
    rows += [Spacer(1,14),Paragraph(f'Avisos ({len(alerts)})',styles['Heading1'])]
    if alerts:rows.append(table([['Fecha','Canal','Tipo','Detalle']]+[[dt.isoformat(sep=' '),sesion.nombre(c),k,d] for dt,c,k,d in alerts],[125,235,190,220]))
    else:rows.append(par('No se detectaron avisos con los parámetros actuales.'))
    if r.notas:rows += [Spacer(1,12),Paragraph('Observaciones de importación',styles['Heading1'])]+[par(x) for x in r.notas]
    def footer(canvas,doc):
        canvas.setFont('HornoSans',8);canvas.setFillColor(colors.grey);canvas.drawString(35,18,'Visor de horno | '+datetime.now().strftime('%d/%m/%Y %H:%M'));canvas.drawRightString(805,18,str(doc.page))
    doc.build(rows,onFirstPage=footer,onLaterPages=footer)
