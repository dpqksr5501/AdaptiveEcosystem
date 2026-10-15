from pathlib import Path
from math import atan2, cos, sin, pi
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from PIL import Image
from pypdf import PdfReader
import shutil
import json

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'tmp/pdfs/mentor'
OUT=ROOT/'output/pdf/AdaptiveEcosystem_시스템설명_멘토검토용.pdf'
CANDIDATE=WORK/'redesigned.pdf'
pdfmetrics.registerFont(TTFont('Body','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('Bold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFont(TTFont('Title','C:/Windows/Fonts/batang.ttc',subfontIndex=0))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold')
W,H=A4;M=49;CW=W-2*M
INK='#272B28';GREY='#69716A';GREEN='#526A51';LIGHT='#CFD6CC';PAPER='#FFFFFC'
C=canvas.Canvas(str(CANDIDATE),pagesize=A4,pageCompression=1)
C.setTitle('AdaptiveEcosystem - 생태계 시스템 설명')
C.setAuthor('AdaptiveEcosystem 팀')
checks=[]

def line(x1,y1,x2,y2,color=LIGHT,width=.6):
    C.setStrokeColor(colors.HexColor(color));C.setLineWidth(width);C.line(x1,H-y1,x2,H-y2)

def text(x,y,s,size=11,font='Body',color=INK):
    C.setFillColor(colors.HexColor(color));C.setFont(font,size);C.drawString(x,H-y-size,s)
    assert x+pdfmetrics.stringWidth(s,font,size)<=W-M+1, s

def p(x,y,w,s,size=11,color=INK,leading=None,maxh=150):
    st=ParagraphStyle('body',fontName='Body',fontSize=size,leading=leading or size*1.8,
        wordWrap='CJK',textColor=colors.HexColor(color))
    para=Paragraph(s,st);_,h=para.wrap(w,1000)
    assert h<=maxh,(s,h,maxh)
    assert y+h< H-53,(s,y+h)
    para.drawOn(C,x,H-y-h)
    checks.append({'page':C.getPageNumber(),'y':y,'h':h,'text':s})
    return h

def arrow(x1,y1,x2,y2):
    line(x1,y1,x2,y2,GREEN,1)
    a=atan2(y2-y1,x2-x1);r=5
    line(x2,y2,x2-r*cos(a-pi/6),y2-r*sin(a-pi/6),GREEN,1)
    line(x2,y2,x2-r*cos(a+pi/6),y2-r*sin(a+pi/6),GREEN,1)

def page(n,title,sub):
    C.setFillColor(colors.HexColor(PAPER));C.rect(0,0,W,H,fill=1,stroke=0)
    text(M,27,'AdaptiveEcosystem',9,'Body',GREEN)
    text(W-145,27,'2026. 10. 11.',8.5,'Body',GREY)
    line(M,52,W-M,52)
    text(M,77,title,25,'Title')
    p(M,119,CW,sub,10.1,GREY,maxh=40)
    line(M,H-49,W-M,H-49)
    text(M,H-33,'생태계 시스템 설명',8,'Body',GREY)
    text(W-M-9,H-33,str(n),8,'Body',GREY)

def end():C.showPage()

def image(path,x,y,w,h,crop=None):
    iw,ih=Image.open(path).size
    C.saveState();clip=C.beginPath();clip.rect(x,H-y-h,w,h);C.clipPath(clip,stroke=0,fill=0)
    if crop:
        l,t,r,b=crop;scale=min(w/(r-l),h/(b-t))
        dx=x+(w-(r-l)*scale)/2-l*scale
        dy=H-y-h+(h-(b-t)*scale)/2-(ih-b)*scale
    else:
        scale=min(w/iw,h/ih);dx=x+(w-iw*scale)/2;dy=H-y-h+(h-ih*scale)/2
    C.drawImage(str(path),dx,dy,width=iw*scale,height=ih*scale)
    C.restoreState()

def plant(x,ground,height,color):
    line(x,ground,x-2,ground-height,color,1.1)
    for frac,side in [(.32,-1),(.52,1),(.74,-1),(.88,1)]:
        yy=ground-height*frac
        C.setFillColor(colors.HexColor(color));q=C.beginPath()
        q.moveTo(x-1,H-yy)
        q.curveTo(x+side*height*.24,H-(yy-height*.11),x+side*height*.31,H-(yy-height*.27),x+side*height*.27,H-(yy-height*.29))
        q.curveTo(x+side*height*.06,H-(yy-height*.22),x-1,H-yy,x-1,H-yy)
        C.drawPath(q,fill=1,stroke=0)

def section(y,title,body,maxh=100):
    text(M,y,title,13,'Bold',GREEN)
    p(M,y+28,CW,body,11,maxh=maxh)

early=ROOT/'AdaptiveEcosystem/Saved/Screenshots/WindowsEditor/HighresScreenshot00004.png'
old=ROOT/'Deliverables/WeeklyReport_20261009/.build/previous'

# 1. Introduction.
page(1,'환경과 함께 변하는 생태계','프로젝트 소개')
p(M,172,CW,'저희는 날씨와 지역 환경에 따라 식물이 자라고, 동물들이 먹이와 위험에 반응하며 살아가는 생태계를 만들고 있습니다. 동물의 행동은 다시 식생과 개체군에 영향을 주도록 구성하려고 합니다.',11.5,maxh=85)
image(early,M,267,CW,225,crop=(190,230,1020,610))
p(M,504,CW,'초기 동물 표현 테스트 화면',9,GREY,maxh=20)
section(552,'만들고 싶은 모습',
    '비가 내리고 성장 조건이 좋아지면 풀이 더 크게 자라거나 빽빽해지고, 동물들은 달라진 먹이와 주변 환경에 맞춰 움직입니다. 먹이를 찾아 모인 동물들이 풀을 먹으면 그 지역의 자원이 줄고, 이후 식생이 회복되거나 동물들이 다른 지역으로 이동하는 흐름을 생각하고 있습니다.',maxh=100)
p(M,699,CW,'이 자료는 팀이 만들고 싶은 전체 시스템을 설명합니다. 현재 연결한 기능과 앞으로 구현할 부분은 마지막 페이지에 정리했습니다.',10.2,GREY,maxh=60)
end()

# 2. Weather and vegetation, drawn as a clearly identified explanatory figure.
page(2,'날씨에 따라 식물도 달라집니다','환경과 식생')
p(M,174,CW,'식물은 배경으로만 두지 않고 생태계의 먹이와 숨을 공간으로 활용하려고 합니다. 강수량과 수분, 온도에 따라 성장과 회복 정도가 달라지고, 그 결과가 식물의 크기와 밀도에도 보이도록 만드는 것이 목표입니다.',11,maxh=82)
left=M;right=315
text(left,275,'성장이 제한되는 환경',12,'Bold',GREY)
text(right,275,'성장 조건이 좋은 환경',12,'Bold',GREEN)
line(left,420,left+218,420,'#A79C85',1)
line(right,420,right+218,420,'#A79C85',1)
for xx,hh in [(18,28),(61,42),(114,30),(177,37)]:plant(left+xx,419,hh,'#A39676')
for i,hh in enumerate([65,95,76,105,68,88,111,80,98,70,89,104]):
    plant(right+10+i*17,419,hh,['#718A61','#536C49','#889C72'][i%3])
arrow(278,367,307,367)
p(left,438,218,'수분이 부족하거나 온도가 맞지 않으면<br/>성장이 느려지고 식생이 줄어드는 모습',9.5,GREY,maxh=40)
p(right,438,218,'수분과 온도가 성장에 적합하면<br/>식물이 커지고 밀도가 높아지는 모습',9.5,GREY,maxh=40)
p(M,493,CW,'식생 변화 예시를 그린 설명 그림입니다.',8.7,GREY,maxh=20)
section(539,'식생의 변화는 동물에게도 영향을 줍니다',
    '풀이 늘면 먹이가 풍부해지고, 수풀이 커지거나 빽빽해지면 주변을 보는 조건과 숨을 공간도 달라질 수 있습니다. 반대로 동물들이 한곳에서 계속 먹이를 먹으면 자원이 줄어들고, 회복을 기다리거나 다른 곳을 찾게 됩니다.',maxh=85)
line(M,665,W-M,665)
text(M,680,'지역 구성',11,'Bold')
p(M+95,680,CW-95,'숲·초원 / 황무지 / 고지대·설원<br/>지역마다 다른 식생과 환경 조건을 행동에 연결할 계획입니다.',10.2,maxh=55)
end()

# 3. Policy decisions with simple ruled lists rather than cards.
page(3,'동물은 자기 상황을 보고 행동합니다','학습과 행동')
p(M,173,CW,'동물에게 정해진 이동만 반복시키기보다, 주변 먹이와 위험, 자신의 에너지 상태를 보고 행동을 선택하게 하려고 합니다. 초식동물의 행동에는 PPO로 학습한 정책을 사용합니다.',11,maxh=85)
text(M,277,'판단에 사용하는 정보',13,'Bold',GREEN)
obs=[('주변 먹이의 밀도','포식자 수와 거리'),('주변 동종 개체 수','현재 에너지'),('최근 포식 이력','은신처까지의 거리')]
for i,(a,b) in enumerate(obs):
    y=310+i*35;line(M,y-7,W-M,y-7)
    text(M+4,y,a,11);text(M+CW/2+12,y,b,11)
line(M,410,W-M,410)
text(M,436,'선택하는 행동',13,'Bold',GREEN)
p(M,466,CW,'먹이를 찾기 / 무리와 모이기 / 위험에서 도망가기 / 은신처로 향하기',11,maxh=45)
section(524,'학습과 게임 실행을 나눕니다',
    'Python 환경에서 행동을 학습하고, 학습된 가중치를 Unreal C++로 가져와 실행합니다. 같은 모델을 공유하더라도 각 동물의 관측이 다르기 때문에 행동 결과는 달라집니다. 무리 경보와 은신처 상황은 이후 Social 시스템에서 행동에 반영합니다.',maxh=95)
line(M,665,W-M,665)
p(M,683,CW,'환경·식생 변화 → 개체의 판단 → 이동·섭식·포식 → 자원·개체군 변화<br/>이 결과가 다음 판단에 다시 들어오는 순환을 완성하는 것이 목표입니다.',10.3,GREEN,maxh=60)
end()

# 4. Social behavior with genuine historical screenshots.
page(4,'위험을 느끼면 무리와 함께 반응합니다','감각·무리·은신처')
p(M,173,CW,'사슴은 시야와 소리로 위협을 감지하고, 기억한 정보와 무리 경보를 바탕으로 도망가거나 은신처를 찾습니다. 늑대는 직접 보거나 들은 먹잇감의 단서를 추적합니다.',11,maxh=82)
text(M,275,'감지',12,'Bold',GREEN);text(M+160,275,'경보 공유',12,'Bold',GREEN);text(M+340,275,'도주·은신',12,'Bold',GREEN)
arrow(M+63,286,M+140,286);arrow(M+243,286,M+320,286)
image(old/'p5_0_I1.png',M,322,238,144)
image(old/'p6_0_I1.png',M+259,322,238,144)
p(M,479,238,'초기 무리·경보 테스트',9,GREY,maxh=20)
p(M+259,479,238,'초기 차폐·은신처 예약 테스트',9,GREY,maxh=20)
section(532,'무리가 공유하는 위험과 개인의 기억',
    '위험 정보는 무리 안에서 전달되고 시간이 지나면 약해집니다. 시야에서 사라진 대상은 마지막으로 감지한 위치를 기억하며, 대상의 현재 위치를 계속 아는 방식으로 처리하지 않습니다.',maxh=80)
section(656,'은신처는 선택한 뒤에도 관리합니다',
    '여러 개체가 같은 자리를 사용하지 않도록 슬롯을 예약합니다. 실제 도착을 확인해 점유로 바꾸고, 이동 실패나 은신 요구 종료, 사망·삭제·이주가 발생하면 자리를 반환합니다.',maxh=72)
end()

# 5. System roles and runtime.
page(5,'각 기능을 하나의 실행 흐름으로 연결합니다','시스템 구성')
p(M,173,CW,'지역 환경, 생태 상태, 동물의 판단과 이동은 역할을 나누어 구현하고 있습니다. 동물의 상태와 화면 표현을 분리하고, 실제 위치를 갱신하는 이동 경로는 개체별 하나로 유지합니다.',11,maxh=85)
rows=[('환경·레벨','날씨, 낮밤, 지형과 지역 경계'),
      ('생태계·Mass','먹이 양, 개체 상태와 지역별 개체군'),
      ('학습·정책','개체별 관측과 학습된 행동'),
      ('Social·감각','위협 인지, 무리 경보와 은신처 의도'),
      ('이동','조향과 위치 갱신, 도착·실패 결과'),
      ('네트워크·표현','결과 전달, 동물 외형과 애니메이션·발소리')]
for i,(a,b) in enumerate(rows):
    y=276+i*43;line(M,y-10,W-M,y-10)
    text(M,y,a,11,'Bold',GREEN);text(M+149,y,b,10.5)
line(M,535,W-M,535)
section(568,'생태계 판단은 서버에서 진행합니다',
    '서버 또는 Standalone이 자원과 개체 상태, 감각과 무리 행동을 계산합니다. 클라이언트는 전달받은 이동 결과를 동물 BP와 애니메이션으로 보여주고 발소리를 재생합니다.',maxh=80)
p(M,691,CW,'팀 레벨의 초기 테스트 구성은 사슴 16마리와 늑대 3마리입니다. 은신처는 숲에 2곳을 배치했고, 동물은 실행 중 생성되어 논리 상태를 표현합니다.',10.5,GREY,maxh=62)
end()

# 6. Current and planned behavior, without references or implementation labels.
page(6,'현재 진행 상황과 남은 작업','진행 상황')
section(176,'현재 연결한 부분',
    '초식동물의 학습된 행동에 무리 경보와 은신처 의도를 반영하고, 기존 이동 시스템이 이를 실행하도록 연결했습니다. 은신처까지 이동한 뒤 점유 상태로 바뀌고, 사망이나 요구 종료 시 자리를 반환하는 흐름도 확인했습니다.',maxh=100)
p(M,310,CW,'사슴과 늑대의 감각·기억, 동물 애니메이션과 발소리를 적용했습니다. 팀 레벨에서 동작을 확인했고, 서버·클라이언트 연결과 재접속도 테스트했습니다.',11,maxh=100)
line(M,435,W-M,435)
section(464,'앞으로 연결할 부분',
    '지역 날씨와 수분·온도를 식물의 성장과 회복에 연결하고, 크기와 밀도의 변화를 먹이 양과 은신 환경에도 반영할 계획입니다. 낮밤에 따른 행동 변화와 시각적인 환경 변화도 같은 흐름 안에서 맞춰야 합니다.',maxh=100)
p(M,597,CW,'물은 현재 진입을 제한하는 단계이며, 갈증이나 마시기 행동은 후속 범위입니다. 장애물 우회, 학습 환경과 게임의 조건 차이, 많은 개체와 장시간 실행에서의 성능도 추가로 검증하려고 합니다.',11,maxh=100)
p(M,713,CW,'전체 자원·생존·포식·이주 순환의 완성은 남은 통합 목표입니다.<br/>진행 상황은 2026.10.08 구현·검증 기록을 기준으로 정리했습니다.',9.3,GREY,maxh=47)
end()
C.save()
reader=PdfReader(CANDIDATE)
assert len(reader.pages)==6
content='\n'.join(q.extract_text() for q in reader.pages)
for required in ['식물','크기','밀도','강수량','수분','온도','PPO','진행 상황']:
    assert required in content,required
for forbidden in ['자료와 그림의 출처','Docs/','[1]','[2]','opt-in','Source','Golden Vector']:
    assert forbidden not in content,forbidden
shutil.copyfile(CANDIDATE,OUT)
(WORK/'redesign_layout.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
(WORK/'redesign_text.txt').write_text(content,encoding='utf-8')
print(json.dumps({'pages':6,'bytes':OUT.stat().st_size,'output':str(OUT)},ensure_ascii=False))
