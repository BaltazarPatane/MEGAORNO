"""Gráficas con límites explícitos: una sola fecha nunca amplía el eje a años."""
from datetime import datetime, timedelta, timezone
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter, DateFormatter, date2num
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
from models import fecha_local

COLORS=['#ff4040','#2274aa','#32916a','#9461ad','#d06b32','#ad3c60','#617d3b','#4c6b87','#9e770d','#3d9497','#664494','#a35135']


def time_bounds(samples,profile,full_program=False,window_minutes=0):
    start=samples[0][0] if samples else datetime.now().replace(microsecond=0)
    end=samples[-1][0] if samples else start
    if window_minutes:
        start=max(start,end-timedelta(minutes=window_minutes))
    elif full_program and samples:
        end=max(end,start+timedelta(minutes=profile.desfase+sum(profile.tiempos)))
    span=(end-start).total_seconds()
    if span<60:
        middle=start+(end-start)/2
        return middle-timedelta(seconds=30),middle+timedelta(seconds=30)
    padding=timedelta(seconds=max(2,span*.04))
    return start-padding,end+padding


def y_bounds(values,minimum_pad):
    if not values:return (0,1)
    low,high=min(values),max(values);padding=max(minimum_pad,(high-low)*.08)
    return low-padding,high+padding


def render_chart(fig,ax_t,ax_v,session,selected,unit='°C/h',mode='Temperatura',
                 show_ideal=False,show_band=False,full_program=False,window_minutes=0):
    """Devuelve las series con valores válidos para el cursor de la interfaz."""
    r,p=session.registro,session.perfil
    ax_t.clear();ax_v.clear()
    grid=ax_t.get_subplotspec().get_gridspec()
    both=mode=='Ambas'
    ax_t.set_subplotspec(grid[0] if both else grid[:])
    ax_v.set_subplotspec(grid[1] if both else grid[:])
    ax_t.set_visible(mode!='Velocidad');ax_v.set_visible(mode!='Temperatura')
    axes=(ax_t,ax_v);active=ax_t if mode=='Temperatura' else ax_v
    start,end=time_bounds(r.muestras,p,full_program,window_minutes)
    xlim=date2num([start,end]);factor=60 if unit=='°C/h' else 1
    selected=[i for i in selected if 0<=i<len(r.canales)]
    series={ax_t:[],ax_v:[]};visible_values={ax_t:[],ax_v:[]}
    for ax in axes:
        ax.set_facecolor('white')
        ax.grid(which='major',color='#d0d0d0',linewidth=.7)
        ax.grid(which='minor',color='#eeeeee',linewidth=.45)
        ax.yaxis.set_minor_locator(AutoMinorLocator(2));ax.yaxis.set_major_locator(MaxNLocator(nbins=8 if both else 12))
        ax.tick_params(axis='both',labelsize=8)
        for spine in ax.spines.values():spine.set_color('#777777');spine.set_linewidth(.7)
    ax_t.set_ylabel('Grados Celsius (°C)',color='#ff4040' if len(selected)==1 else '#333333')
    ax_v.set_ylabel('Velocidad ('+unit+')')
    for idx in selected:
        channel=r.canales[idx];x=[];temperatures=[];rates=[];previous=None
        for i,(dt,values) in enumerate(r.muestras):
            if channel not in values:continue
            if previous is not None and (dt-previous).total_seconds()/60>p.hueco_max:
                x.append(dt);temperatures.append(None);rates.append(None)
            rate=r.velocidades[i].get(channel)
            x.append(dt);temperatures.append(values[channel]);rates.append(None if rate is None else rate*factor);previous=dt
        color='#ff4040' if len(selected)==1 else COLORS[idx%len(COLORS)]
        for ax,values in [(ax_t,temperatures),(ax_v,rates)]:
            points=[(float(date2num(dt)),float(value)) for dt,value in zip(x,values) if value is not None]
            if not points:continue
            # Marcador sólo para que la primera lectura sea visible sin inventar una línea.
            ax.plot(x,values,color=color,lw=.85,marker='o' if len(points)==1 else None,markersize=3,label=session.nombre(channel))
            series[ax].append(dict(name=session.nombre(channel),color=color,x=[v[0] for v in points],y=[v[1] for v in points]))
            visible_values[ax].extend(y for t,y in points if xlim[0]<=t<=xlim[1])
    if r.muestras:
        origin=r.muestras[0][0]
        if show_ideal:
            up,hold,down=p.tiempos
            left=(start-origin).total_seconds()/60;right=(end-origin).total_seconds()/60
            knots=sorted(set([left,right]+[v for v in [0,p.desfase,p.desfase+up,p.desfase+up+hold,p.desfase+up+hold+down] if left<=v<=right]))
            ideal=[p.punto(v)[0] for v in knots]
            ax_t.plot([origin+timedelta(minutes=v) for v in knots],ideal,color='#243d4a',ls='--',lw=1,label='Curva ideal')
            visible_values[ax_t].extend(ideal)
            limits=(-p.bajada/60*factor,p.subida/60*factor)
            for i,value in enumerate(limits):ax_v.axhline(value,color='#608476',ls='--',lw=.8,label='Límites de rampa' if i==0 else None)
            visible_values[ax_v].extend(limits)
        if show_band:
            ax_t.axhspan(p.inferior,p.superior,color='#7ea58c',alpha=.16,label='Banda de mantenimiento')
            visible_values[ax_t].extend([p.inferior,p.superior])
        for event in session.controladores:
            ax_t.axvline(fecha_local(event['fecha']),color='#aaaaaa',lw=.6,alpha=.6)
    ax_t.set_ylim(*y_bounds(visible_values[ax_t],.5));ax_v.set_ylim(*y_bounds(visible_values[ax_v],.1))
    ax_v.axhline(0,color='#aaaaaa',lw=.65)
    # Se aplica al final, después de TODAS las curvas y anotaciones y al eje compartido.
    ax_v.set_xlim(*xlim)
    locator=AutoDateLocator(minticks=4,maxticks=10,interval_multiples=True,tz=timezone.utc)
    ax_v.xaxis.set_major_locator(locator)
    if (end-start).total_seconds()<=2*86400:
        ax_v.xaxis.set_major_formatter(DateFormatter('%H:%M:%S\n%d/%m/%Y',tz=timezone.utc))
        ax_v.xaxis.set_minor_locator(AutoMinorLocator(2))
    else:ax_v.xaxis.set_major_formatter(ConciseDateFormatter(locator,tz=timezone.utc))
    ax_t.tick_params(axis='x',labelbottom=mode=='Temperatura')
    active.set_xlabel('Hora local de medición')
    for ax in axes:
        if not ax.get_visible():continue
        if len(series[ax])>1 or show_ideal or (show_band and ax is ax_t):
            handles,labels=ax.get_legend_handles_labels()
            if handles:ax.legend(loc='upper left',fontsize=7,ncol=min(3,len(handles)),framealpha=.85)
        if not series[ax]:
            if not r.muestras:text='Esperando muestras de la adquisición…'
            elif not selected:text='Seleccioná un canal en la lista de la izquierda.'
            elif ax is ax_v:text='La velocidad requiere dos muestras válidas consecutivas.'
            else:text='Los canales seleccionados no tienen temperaturas válidas.'
            ax.text(.5,.5,text,transform=ax.transAxes,ha='center',va='center',fontsize=10,color='#506571',wrap=True)
    return series
