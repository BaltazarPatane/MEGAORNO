// Portable executable tests for the same gate compiled into the WCF bridge.
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Web.Script.Serialization;
using HornoWcf;

class PollGateTests {
    static int checks=0;
    static void Check(bool condition,string message) {
        if(!condition)throw new Exception(message);
        checks++;Console.WriteLine("OK: "+message);
    }
    static void Main(string[] args) {
        if(args.Length>0 && args[0]=="--stream") { Stream();return; }
        var gate=new PollGate();int ticket;
        var events=new List<string>();var json=new JavaScriptSerializer();
        Action<string,object> emit=(kind,data)=>events.Add(kind+":"+json.Serialize(data));
        Check(gate.Next(out ticket) && ticket==0,"Initial poll interval");
        gate.Publish(ticket,"mt_reading","first",emit);
        Check(events.Count==1 && events[0].Contains("\"epoch\":0"),"Epoch accompanies a published measurement");
        gate.SetPaused(true,1);
        gate.Publish(0,"mt_reading","late",emit);
        Check(events.Count==1,"An in-flight response is dropped during pause");
        var entered=new ManualResetEvent(false);var acquired=new ManualResetEvent(false);
        int resumed=-1;
        var waiter=new Thread(()=>{entered.Set();if(gate.Next(out resumed))acquired.Set();});
        waiter.IsBackground=true;waiter.Start();
        Check(entered.WaitOne(1000) && !acquired.WaitOne(100),"No new request starts while paused");
        gate.SetPaused(false,2);
        Check(acquired.WaitOne(1000) && resumed==2,"Resume releases the same waiting gate");waiter.Join();
        gate.Publish(0,"mt_reading","late after resume",emit);
        gate.Publish(1,"mt_waiting","late waiting",emit);
        gate.Publish(2,"mt_reading","current",emit);
        Check(events.Count==2 && events[1].Contains("current"),"Rapid resume never accepts an old interval");
        gate.SetPaused(true,1);
        Check(gate.Next(out ticket) && ticket==2,"An old command cannot pause a newer interval");
        var delayStarted=new ManualResetEvent(false);var delayFinished=new ManualResetEvent(false);
        var delay=new Thread(()=>{delayStarted.Set();gate.WaitInterval(60000,2);delayFinished.Set();});
        delay.IsBackground=true;delay.Start();delayStarted.WaitOne(1000);gate.SetPaused(true,3);
        Check(delayFinished.WaitOne(1000),"Pause interrupts a long polling delay");delay.Join();
        gate.SetPaused(false,4);gate.Publish(2,"mt_reading","stale",emit);
        gate.Publish(4,"mt_reading","latest",emit);
        Check(events.Count==3,"Repeated pause/resume accepts only the newest interval");
        gate.Close();Check(!gate.Next(out ticket),"Closing stops a paused or running gate");
        var commands=new PollGate();int errors=0;
        commands.ReadCommands(new StringReader("{\"command\":\"pause\",\"epoch\":1}\n{\"command\":\"resume\",\"epoch\":2}\n"),(kind,data)=>{if(kind=="error")errors++;});
        Check(errors==0 && !commands.Next(out ticket),"Line protocol processes commands and exits on EOF");
        var bad=new PollGate();
        bad.ReadCommands(new StringReader("invalid secret command\n"),(kind,data)=>{
            if(kind=="error")errors++;
            if(Convert.ToString(data).Contains("secret"))throw new Exception("Command contents leaked");
        });
        Check(errors==1 && !bad.Next(out ticket),"Malformed control fails closed without exposing input");
        Console.WriteLine("Passed "+checks+" PollGate checks.");
    }

    static void Stream() {
        // Test fixture for the Python/stdin/stdout boundary, not a WCF server.
        var json=new JavaScriptSerializer();json.DeserializeObject(Console.ReadLine());
        var outputLock=new object();
        Action<string,object> emit=(kind,data)=>{
            lock(outputLock) {Console.WriteLine(json.Serialize(new {type=kind,data=data}));Console.Out.Flush();}
        };
        var gate=new PollGate();var input=new Thread(()=>gate.ReadCommands(Console.In,emit));
        input.IsBackground=true;input.Start();emit("mt_devices",new[]{"R59022"});
        int ticket,index=0;
        while(gate.Next(out ticket)) {
            Thread.Sleep(10); // Simulate a request that can still be in flight.
            var reading=new {serial="R59022",timestamp=new DateTime(2026,10,6,8,0,0).AddSeconds(30*index).ToString("o"),
                channels=new[]{new {position=2,unit="Celsius",status="Valid",value=(630+index).ToString()}}};
            index++;gate.Publish(ticket,"mt_reading",reading,emit);gate.WaitInterval(100,ticket);
        }
    }
}
