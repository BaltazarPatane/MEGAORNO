// Pause polling without closing the authenticated WCF channel.
// An epoch identifies each acquisition interval; late results cannot cross it.
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Web.Script.Serialization;

namespace HornoWcf {
public sealed class PollGate {
    readonly object sync=new object();
    bool paused=false,closed=false;
    int epoch=0;

    public void ReadCommands(TextReader input,Action<string,object> emit) {
        var reader=new JavaScriptSerializer();
        try {
            string line;
            while((line=input.ReadLine())!=null) {
                var command=reader.Deserialize<Dictionary<string,object>>(line);
                string action=Convert.ToString(command["command"]);
                int next=Convert.ToInt32(command["epoch"]);
                if(action!="pause" && action!="resume")throw new Exception("Control de adquisición desconocido.");
                SetPaused(action=="pause",next);
            }
        }catch(Exception) {
            emit("error","Se interrumpió el control de pausa del puente WCF. La captura se conserva.");
        }finally { Close(); }
    }

    public void SetPaused(bool value,int next) {
        lock(sync) {
            if(next<=epoch)return;
            paused=value;epoch=next;Monitor.PulseAll(sync);
        }
    }

    public void Close() {
        lock(sync) { closed=true;Monitor.PulseAll(sync); }
    }

    public bool Next(out int ticket) {
        lock(sync) {
            while(paused && !closed)Monitor.Wait(sync);
            ticket=epoch;return !closed;
        }
    }

    public void Publish(int ticket,string kind,object data,Action<string,object> emit) {
        lock(sync) {
            if(!closed && !paused && ticket==epoch)
                emit("mt_stream",new {epoch=ticket,type=kind,data=data});
        }
    }

    public void WaitInterval(int milliseconds,int ticket) {
        lock(sync) {
            // A pause or resume interrupts the delay, even with a long poll period.
            if(!closed && !paused && ticket==epoch)Monitor.Wait(sync,milliseconds);
        }
    }
}
}
