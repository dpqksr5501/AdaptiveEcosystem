"""Deterministic JYU surface variations derived from project footstep recordings.
Alarm is a synthetic two-tone presentation cue, not an animal voice recording.
"""
from pathlib import Path
import wave, array, math, random
project=Path(__file__).resolve().parents[2]
source=project/'Content/Audio/Footsteps/Dry/SW_Dry_Dry1.wav'
with wave.open(str(source),'rb') as f:
    rate=f.getframerate();channels=f.getnchannels();width=f.getsampwidth()
    if width!=2: raise ValueError('Expected PCM16 source')
    pcm=array.array('h',f.readframes(f.getnframes()))
mono=[sum(pcm[i:i+channels])/channels/32768 for i in range(0,len(pcm),channels)]
out=project/'Content/JYU/Audio/Source';out.mkdir(parents=True,exist_ok=True)
def save(name,values):
    samples=array.array('h',[round(max(-.95,min(.95,v))*32767) for v in values])
    with wave.open(str(out/(name+'.wav')),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(samples.tobytes())
for kind in ('Snow','Water','Wet'):
    rng=random.Random(510);low=0.;values=[]
    for i,x in enumerate(mono):
        t=i/rate;low+=.09*(x-low);env=math.exp(-t*12)
        if kind=='Snow': value=.65*low+.04*rng.uniform(-1,1)*env
        elif kind=='Water': value=.35*x+.06*rng.uniform(-1,1)*env+.035*math.sin(2*math.pi*(450*t-180*t*t))*env
        else: value=.5*low+.035*rng.uniform(-1,1)*env
        values.append(value)
    save(kind,values)
values=[]
for i in range(round(rate*.6)):
    t=i/rate;envelope=max(0,math.sin(math.pi*t/.6))**2
    values.append(.1*envelope*(math.sin(2*math.pi*(680*t+180*t*t))+.3*math.sin(2*math.pi*1240*t)))
save('Alarm',values)
print('Created four JYU PCM16 mono cues:',out)
