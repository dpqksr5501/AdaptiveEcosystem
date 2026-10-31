"""Compare the actual native leaf model with the Python mirror. No Unreal or learning process."""
import hashlib,json,random,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'herbivore_rl'))
from env_v2.vegetation_v1 import Config,Weather,Habitat,Cell,advance

def main():
    exe=Path(sys.argv[1]);output=Path(sys.argv[2]);rng=random.Random(20261023)
    rows=[];expected=[]
    for i in range(2400):
        capacity=rng.uniform(0,3);food=rng.uniform(0,capacity)
        enabled=int(i%17!=0);plant=i%4
        c=Config(bool(enabled),.018,.002,.010,.001,.004)
        w=Weather(rng.random(),rng.choice((-50,0,20,40,70)),rng.random())
        h=Habitat(plant,rng.random(),rng.random(),rng.random(),rng.random(),i%11!=0)
        s=Cell(rng.choice((0.,1.,rng.random())),rng.random())
        dt=rng.choice((0.,.1,2/15,.25,.3))
        row=[enabled,c.infiltration,c.evaporation,c.drainage,c.uptake,c.stress_loss,w.rain,w.temperature,w.light,
             plant,h.drainage,h.shade,h.water_supply,h.flood,int(h.ground_usable),s.moisture,s.stress,food,capacity,rng.uniform(0,.1),dt]
        result=advance(c,w,h,s,food,capacity,row[19],dt)
        rows.append(' '.join(format(v,'.17g') for v in row));expected.append((*result,s.moisture,s.stress))
    result=subprocess.run([str(exe)],input='\n'.join(rows)+'\n',text=True,capture_output=True,check=True)
    actual=[tuple(map(float,line.split())) for line in result.stdout.splitlines()]
    if len(actual)!=len(expected):raise AssertionError('Native case count mismatch')
    error=max(abs(a-b) for one,two in zip(expected,actual) for a,b in zip(one,two))
    report={'schema':1,'model':'soil-v1 leaf only','cases':len(actual),'seed':20261023,'max_absolute_error':error,
        'native_header_sha256':hashlib.sha256((root/'AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy/EcoVegetationV3.h').read_bytes()).hexdigest(),
        'full_world_parity':False,'retraining_performed':False,'passed':error<1e-12}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not report['passed']:raise AssertionError(report)
    print(json.dumps(report))
if __name__=='__main__':main()
