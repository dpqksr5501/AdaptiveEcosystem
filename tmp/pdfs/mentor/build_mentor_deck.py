from pathlib import Path
from math import atan2,cos,sin,pi
import json,shutil,sys
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from PIL import Image
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT/'tmp/pdfs/mentor'
OUT=ROOT/'output/pdf/AdaptiveEcosystem_시스템설명_멘토검토용.pdf'
CANDIDATE=WORK/'mentor_deck.pdf'
pdfmetrics.registerFont(TTFont('Body','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('Bold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold')
W,H=960,540;M=42;CW=876
INK='#25342E';GREEN='#436E5C';MUTED='#69776E';LINE='#D4DDD6';PAPER='#FCFDF9'
C=canvas.Canvas(str(CANDIDATE),pagesize=(W,H),pageCompression=1)
C.setTitle('AdaptiveEcosystem - 시스템 설명 및 팀 피드백 요청')
C.setAuthor('AdaptiveEcosystem 팀');checks=[]

def text(x,y,s,size=16,bold=False,color=INK):
    font='Bold' if bold else 'Body'
    assert x+pdfmetrics.stringWidth(s,font,size)<=W-M+1,(s,size)
    C.setFillColor(colors.HexColor(color));C.setFont(font,size);C.drawString(x,H-y-size,s)

def p(x,y,w,s,size=15,color=INK,maxh=200,leading=None):
    style=ParagraphStyle('p',fontName='Body',fontSize=size,leading=leading or size*1.65,
        wordWrap='CJK',textColor=colors.HexColor(color))
    q=Paragraph(s,style);_,h=q.wrap(w,1000)
    assert h<=maxh,(C.getPageNumber(),s,h,maxh)
    assert y+h<=H-46,(C.getPageNumber(),s,y+h)
    q.drawOn(C,x,H-y-h);checks.append({'page':C.getPageNumber(),'y':y,'h':h,'text':s})
    return h

def line(x1,y1,x2,y2,color=LINE,width=.7):
    C.setStrokeColor(colors.HexColor(color));C.setLineWidth(width);C.line(x1,H-y1,x2,H-y2)

def arrow(x1,y1,x2,y2):
    line(x1,y1,x2,y2,GREEN,1.3);a=atan2(y2-y1,x2-x1)
    for d in [-1,1]:line(x2,y2,x2-6*cos(a+d*pi/6),y2-6*sin(a+d*pi/6),GREEN,1.3)

def page(n,title,sub):
    C.setFillColor(colors.HexColor(PAPER));C.rect(0,0,W,H,fill=1,stroke=0)
    text(M,29,title,30,True)
    p(M,79,CW,sub,13.2,MUTED,maxh=44)
    line(M,H-34,W-M,H-34)
    text(M,H-23,'AdaptiveEcosystem / 시스템 설명 및 피드백 요청',9,color=MUTED)
    text(W-92,H-23,f'{n:02d} / 11',9,color=MUTED)

def end():C.showPage()

def photo(path,x,y,w,h):
    iw,ih=Image.open(path).size;s=min(w/iw,h/ih)
    C.drawImage(str(path),x+(w-iw*s)/2,H-y-h+(h-ih*s)/2,width=iw*s,height=ih*s)

def head(x,y,s):text(x,y,s,17,True,GREEN)

def plant(x,g,h,col):
    line(x,g,x-2,g-h,col,1.1)
    for f,side in [(.3,-1),(.5,1),(.7,-1),(.88,1)]:
        y=g-h*f;q=C.beginPath();q.moveTo(x,H-y)
        q.curveTo(x+side*h*.28,H-y+h*.16,x+side*h*.32,H-y+h*.28,x+side*h*.28,H-y+h*.28)
        q.curveTo(x+side*h*.06,H-y+h*.2,x,H-y,x,H-y)
        C.setFillColor(colors.HexColor(col));C.drawPath(q,fill=1,stroke=0)

ASSET=WORK/'attached'

page(1,'환경과 함께 변하는 생태계','비·눈과 낮밤에 따라 식생과 몬스터의 행동이 달라지는 생태계를 만들고 있습니다.')
photo(ASSET/'page1_image1.jpg',M,143,386,257)
p(M,410,386,'초기 사슴 표현 테스트 화면',11,MUTED,maxh=20)
head(474,142,'만들고 싶은 모습')
p(474,177,444,'비·눈에 따라 식생과 먹이 조건이 달라지고, 낮과 밤에 따라 생물의 행동 성향도 바뀌게 하려고 합니다. 몬스터는 각자 처한 상황을 보고 행동을 선택합니다.',16,maxh=110)
p(474,291,444,'먹이가 떨어지면 먹이가 있는 다른 지역으로 이주합니다. 먹이를 먹거나 이주하면서 자원과 개체군이 달라지고, 그 변화가 다음 판단에 영향을 주게 하려고 합니다.',16,maxh=110)
line(M,448,W-M,448)
p(M,464,CW,'환경과 식생이 행동에 영향을 주고, 섭식과 이주 결과가 다시 지역 상태에 반영됩니다.',15,GREEN,maxh=30)
end()

page(2,'날씨와 낮밤이 생태계의 조건을 바꿉니다','비·눈에 따라 식생이 달라지고, 낮밤에 따라 생물의 활동과 행동 성향도 바뀌도록 만들 계획입니다.')
head(M,143,'식생 변화 예시')
line(M,359,242,359,'#A5967B',1);line(278,359,478,359,'#A5967B',1)
for xx,hh in [(22,30),(68,43),(119,27),(172,36)]:plant(M+xx,358,hh,'#A19477')
for i,hh in enumerate([61,89,75,98,66,85,105,72,94,68]):plant(288+i*18,358,hh,['#6E8B59','#486E4D','#839A6A'][i%3])
arrow(246,299,269,299)
text(M+5,383,'식생이 적은 상태',13,color=MUTED)
text(278,383,'커지고 빽빽해진 상태',13,color=MUTED)
p(M,417,436,'날씨에 따른 식생 변화를 설명하기 위한 그림입니다.',11,MUTED,maxh=23)
head(529,144,'비·눈과 식생')
p(529,181,389,'비가 내리면 식물이 커지거나 빽빽해지게 하려고 합니다. 눈이 내릴 때도 식생의 모습과 먹이 조건이 달라지도록 만들 계획입니다.',15,maxh=100)
head(529,291,'낮과 밤에 따른 행동 성향')
p(529,327,389,'시간대에 따라 활동하거나 쉬는 정도가 달라지고, 먹이를 찾거나 위험에 반응하는 방식도 바뀌게 하려고 합니다. 구체적인 차이는 종별로 정할 계획입니다.',15,maxh=120)
p(M,466,CW,'지역 구성: 숲·초원 / 황무지 / 고지대·설원',13,GREEN,maxh=25)
end()

page(3,'먹이가 떨어지면 다른 지역으로 이주합니다','같은 개체가 먹이가 있는 인접 지역으로 이동하고, 도착 후 지역별 개체군에 반영됩니다.')
head(M,146,'출발 지역: 먹이 고갈')
head(610,146,'도착 지역: 먹이 있음')
line(M,191,327,191);line(610,191,918,191)
for i in range(5):
    C.setFillColor(colors.HexColor(['#4D7460','#76927B','#A1B19C','#647E69','#89A387'][i]))
    C.circle(M+38+i*45,H-240,9,fill=1,stroke=0)
    C.circle(648+i*45,H-240,9,fill=1,stroke=0)
arrow(354,240,581,240)
text(373,202,'같은 개체가 이동',15,True,GREEN)
text(M,275,'새로 생성하거나 교체하지 않음',13,color=MUTED)
text(610,275,'도착하면 소속 지역과 집계를 변경',13,color=MUTED)
for x,t,b in [(M,'1. 목적지 판단','현재 지역의 먹이가 고갈되면 먹이가 있는 인접 지역을 찾습니다.'),
             (348,'2. 실제 이동','같은 ID로 이동합니다. 갈 곳이 없거나 도착지의 먹이가 떨어지면 대기합니다.'),
             (654,'3. 도착 반영','도착을 확인한 뒤 출발 지역의 개체 수는 줄고, 도착 지역의 개체 수는 늘어납니다.')]:
    head(x,327,t);p(x,360,264,b,14,maxh=75)
p(M,446,CW,'현재는 먹이가 고갈되면 이주하도록 규칙을 두고 있습니다. 군집 이동은 MassFlock을 참고해 UE MassMovement와 연결하려고 합니다. 학습에는 Stable-Baselines3, PyTorch, NumPy 등의 OSS를 사용합니다.',12.3,MUTED,maxh=46)
end()

page(4,'몬스터가 상황을 보고 판단하게 만들고 싶습니다','강화학습 담당자가 정리한 최근 실험 내용입니다. 현재 게임에 적용한 내용은 뒤에서 따로 설명했습니다.')
head(M,142,'같은 신경망, 각자의 관측')
p(M,179,417,'모든 몬스터가 하나의 신경망을 함께 쓰되, 각자 포식자와의 거리와 다가오는 속도, 은신처 위치, 배고픔 등을 보고 판단하도록 했습니다.',15.5,maxh=110)
head(M,302,'학습하는 선택')
p(M,338,417,'먹기 / 도망 / 숨기 / 얼어붙기<br/>보상은 생존·먹이·번식·사망에만 주고, 특정 행동에 직접 점수를 주지는 않았습니다.',15.5,maxh=115)
line(491,145,491,450)
head(529,142,'지금까지 확인한 것')
p(529,179,389,'낮밤을 넣고 밤에는 포식자가 자게 했더니, 밤에 멈춰 쉬는 행동이 학습됐습니다.',15.5,maxh=85)
p(529,270,389,'계속 먹기만 하는 쪽으로 학습이 굳어, 손으로 만든 규칙을 먼저 흉내 낸 뒤 강화학습으로 다듬는 방식으로 바꿨습니다.',15.5,maxh=105)
p(529,392,389,'지금은 단순한 규칙과 다른 판단, 개체마다의 개성을 화면에서 어떻게 보여줄지 고민하고 있습니다.',14.5,GREEN,maxh=70)
end()

page(5,'사슴은 위험을 공유하고, 늑대는 단서를 추적합니다','감각·기억과 무리 경보를 실제 행동으로 연결하고 있습니다.')
head(M,143,'사슴의 위협 감지')
p(M,178,405,'시야와 소리로 위험을 감지하고 무리에 경보를 전달합니다. 경보는 거리에 따라 달라지고 시간이 지나면 약해집니다.',15.5,maxh=105)
head(M,301,'늑대의 먹잇감 감지')
p(M,336,405,'직접 보거나 들은 단서를 따라갑니다. 시야에서 사라지면 마지막으로 감지한 위치를 기억하고, 일정 시간이 지나면 잊습니다.',15.5,maxh=105)
photo(ASSET/'page2_image1.jpg',528,145,346,286)
p(528,447,346,'초기 무리 디버그 화면',11,MUTED,maxh=20)
end()

page(6,'은신처는 선택부터 도착과 반환까지 관리합니다','Social이 목적지와 행동 의도를 전달하면, 기존 이동 시스템이 이동 결과를 알려줍니다.')
steps=[('감지·경보',M),('선택·예약',236),('이동',431),('도착·점유',625),('반환',820)]
for i,(s,x) in enumerate(steps):
    text(x,142,s,17,True,GREEN)
    if i<4:arrow(x+100,155,steps[i+1][1]-17,155)
photo(ASSET/'page4_image1.jpg',M,210,510,253)
p(M,473,510,'초기 차폐·슬롯 예약 테스트 화면',11,MUTED,maxh=20)
p(594,218,324,'같은 자리를 동시에 쓰지 않도록 예약하고, 실제 도착을 확인한 뒤 점유 상태로 바꿉니다.',15.5,maxh=115)
p(594,333,324,'이동에 실패하거나 숨을 필요가 없어지면 예약한 자리를 반환합니다. 사망·삭제·이주 때도 반환합니다. 장애물을 돌아가는 경로 탐색은 앞으로 연결해야 합니다.',15.5,maxh=140)
end()

page(7,'생태계의 상태와 화면 표현을 나누어 관리합니다','현재 팀 프로젝트를 기반으로 다른 Unreal 프로젝트에서도 사용할 수 있는 플러그인을 목표로 합니다.')
head(M,143,'서버가 관리하는 것')
p(M,180,405,'지역의 먹이와 개체군, 개체의 상태와 이동, 감각·무리 경보·은신처 예약을 관리합니다. 화면에서 멀어진 지역도 생태 상태를 유지하게 하려고 합니다.',15.5,maxh=140)
head(529,143,'클라이언트가 보여주는 것')
p(529,180,389,'전달받은 결과를 동물 BP와 애니메이션으로 보여주고 로컬에서 발소리를 재생합니다. 관심 범위의 개체를 화면에 보여주는 일과 서버의 생태 상태를 유지하는 일은 따로 관리합니다.',15.5,maxh=140)
line(M,341,W-M,341)
head(M,365,'플러그인으로 제공하려는 기반')
p(M,402,CW,'지역 자원·생존·사망·이주를 처리하는 생태 Runtime, Mass 구성, 정책·이동 연결 지점, 네트워크와 Editor 도구를 다른 프로젝트에서도 쓸 수 있게 정리하려고 합니다. 구매자가 자신의 종 설정과 레벨, AI, 표현을 연결해 쓰는 형태를 생각하고 있습니다.',15.5,maxh=88)
end()

page(8,'현재 연결한 부분과 앞으로 맞출 부분','게임에 연결한 내용과 팀원이 정리한 최근 학습 실험을 함께 적었습니다.')
head(M,144,'현재 게임에서 연결한 부분')
p(M,183,405,'PPO 행동을 Social에서 보정해 이동으로 넘깁니다. 도착·실패 결과로 은신처 상태를 관리합니다.<br/><br/>팀 3지역 레벨에 사슴 16마리·늑대 3마리와 숲 은신처 2곳을 배치했습니다. 감각, 애니메이션·발소리와 서버·클라이언트 재접속도 확인했습니다.',15,maxh=255)
head(529,144,'남은 연결과 검증')
p(529,183,389,'비·눈에 따른 식생 변화와 낮밤에 따른 행동 성향을 실제 입력에 연결해야 합니다.<br/><br/>최근 학습 실험의 네 행동, 현재 Unreal의 행동 가중치, Social에 전달하는 값의 의미를 맞춰야 합니다.<br/><br/>자원·섭식·생존·포식·이주가 전체 흐름에서 잘 이어지는지도 확인해야 합니다. 오래 실행하거나 개체 수를 늘렸을 때의 동작도 함께 확인할 예정입니다.',15,maxh=280)
p(M,466,CW,'게임 통합 상태는 2026.10.08 기록 기준입니다. 아래 세 페이지에 담당별 피드백 요청을 모았습니다.',11.5,MUTED,maxh=24)
end()

page(9,'서버·네트워크와 제품화에 대한 피드백','장원준 / MassEntity 기반 생태계 플러그인의 구조와 판매 가능성에 대해 의견을 듣고 싶습니다.')
head(M,142,'하려는 것')
p(M,178,257,'개발자가 생태계 기반을 직접 구축하는 시간을 줄이고, 자신의 환경·동물·행동 시스템을 연결할 수 있는 플러그인을 상용 판매하려고 합니다.',14.5,maxh=160)
head(M,332,'고민되는 점')
p(M,368,257,'팀에 마켓 출시 경험이 없어 제품으로 어디까지 제공해야 할지 고민하고 있습니다. 화면 밖 생태계를 유지하는 비용도 함께 고려해야 합니다.',14.5,maxh=105)
line(331,142,331,475)
questions=[('1. 제품으로 출시할 때 무엇부터 준비해야 할까요?',
    '판매할 플러그인에 최소한 어떤 기능이 필요할지 궁금합니다. 도입 편의성과 예제·문서·지원 중 무엇부터 준비하면 좋을지도 조언 부탁드립니다.'),
    ('2. 화면 밖 생태계는 어느 정도까지 계산해야 할까요?',
    '지역 상태를 유지하면서 계산 비용을 줄이고 싶습니다. 개체별 계산과 지역 요약을 어떻게 나누고, Simulation LOD 기준은 어떻게 잡으면 좋을까요?'),
    ('3. 전체 구조와 네트워크 예산은 적절할까요?',
    'Mass 처리, 서버 권위, 관심 개체 복제와 표본 보간 흐름에 모순이나 병목이 없는지 궁금합니다. 연결별 예산과 성능은 어떤 조건에서 확인하면 좋을지도 조언 부탁드립니다.')]
for i,(q,a) in enumerate(questions):
    y=141+i*113;text(364,y,q,16,True,GREEN);p(364,y+33,554,a,14.2,maxh=75)
end()

page(10,'강화학습에 대한 피드백','권신혁 / 강화학습 · 개체가 스스로 판단하고, 규칙 기반 AI와 다르게 똑똑해 보이도록 만들고 싶습니다.')
head(M,140,'지금 막힌 부분')
p(M,177,397,'같은 상황에서 비교하면, 학습한 몬스터는 “먹다가 포식자가 가까우면 도망”이라는 직접 만든 규칙과 약 <b>93% 같은 선택</b>을 합니다. 성적도 거의 같습니다.',14.5,maxh=105)
p(M,286,397,'숨기·얼어붙기는 몇 마리만 할 때는 이득이지만 무리 전체가 하면 손해라 거의 쓰지 않습니다. 화면에서도 규칙 기반과 구분하기 어렵습니다.',14.5,maxh=105)
p(M,399,397,'다음에는 노려보면 포식자가 물러나거나, 한 마리가 놀라면 무리가 반응하는 규칙을 넣어 이런 행동이 실제로 이득이 되게 해보려고 합니다.',13.4,GREEN,maxh=87)
line(477,140,477,475)
qs=[('1. 환경 설계와 학습 방법 중 어디부터 손볼까요?',
    '결과가 단순한 규칙과 비슷해지는 것이 보상·세계 규칙 때문인지, 학습 방법 때문인지 궁금합니다. 원인을 알아보려면 어떤 비교 실험부터 하면 좋을까요?'),
    ('2. 몬스터마다 개성을 주려면 어떤 방식이 현실적일까요?',
    '대담하거나 겁이 많은 개체를 표현하려고 성격값을 입력으로 주는 방법을 생각하고 있습니다. 이 방식과 다른 대안의 장단점이 궁금합니다.'),
    ('3. “똑똑해 보인다”는 것을 어떻게 평가할까요?',
    '점수 외에 어떤 상황·행동을 관찰해야 할지, 실제 게임에서는 규칙 기반과 강화학습을 어떻게 섞어 쓰는지 조언 부탁드립니다.')]
for i,(q,a) in enumerate(qs):
    y=140+i*113;text(511,y,q,15.1,True,GREEN);p(511,y+33,407,a,14,maxh=76)
end()

page(11,'Social·감각과 은신처에 대한 피드백','조연우 / 감각·기억과 무리 경보, 은신처 선택이 자연스러운 행동으로 이어지게 만들고 싶습니다.')
p(M,127,CW,'현재는 경보 상태에 따라 PPO 행동을 보정하고, 은신처의 차폐·거리·슬롯을 평가해 이동으로 넘깁니다. 앞으로 어떤 부분부터 보완하면 좋을지 의견을 듣고 싶습니다.',14.5,maxh=52)
items=[
('1. Social은 학습된 행동을 어디까지 보정할까요?',
 '경보에 따라 먹이 탐색을 줄이고 도주·은신을 강화합니다. 학습한 판단이 잘 드러나려면 행동을 직접 보정하는 방식과 감각·경보를 학습 입력으로 주는 방식을 어떻게 나누면 좋을까요?'),
('2. 무리 반응을 자연스럽게 만들려면 무엇이 필요할까요?',
 '경보를 공유해도 모두 같은 시점에 같은 행동을 하지 않게 하고 싶습니다. 개인 감지와 기억, 반응 지연, 경보 감쇠 중 무엇부터 조정하고 어떤 시연으로 평가하면 좋을까요?'),
('3. 은신처가 가득 차거나 갈 수 없을 때는 어떻게 할까요?',
 '차폐가 좋아도 도달할 수 없거나 슬롯이 부족할 수 있습니다. 이동 담당과 함께 도달 가능성과 혼잡도를 확인하고, 다른 은신처를 찾거나 계속 도망가게 하려면 무엇부터 연결하면 좋을까요?'),
('4. 환경 변화는 감각과 행동에 어떻게 연결할까요?',
 '비·눈, 낮밤과 수풀 밀도에 따라 시야·청각·숨는 효과도 달라지게 하고 싶습니다. 실제 차폐 검사와 수치 보정을 어떻게 나누면 좋을까요? 개체가 늘었을 때 검사 주기와 비용을 확인하는 방법도 궁금합니다.')]
for i,(q,a) in enumerate(items):
    x=M if i%2==0 else 507;y=207+(i//2)*143
    line(x,y-9,x+411,y-9)
    text(x,y,q,14.8,True,GREEN);p(x,y+34,411,a,13.7,maxh=99)
end()
C.save();r=PdfReader(CANDIDATE);assert len(r.pages)==11
content='\n'.join(q.extract_text() for q in r.pages)
for s in ['비·눈','93%','얼어붙기','장원준','권신혁','조연우','Simulation LOD','반응 지연','낮과 밤','MassFlock','다른 지역으로 이주']:
    assert s in content,s
for s in ['수분','온도','자료와 그림의 출처','[1]','Docs/']:
    assert s not in content,s
shutil.copyfile(CANDIDATE,OUT)
(WORK/'mentor_deck_layout.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
(WORK/'mentor_deck_text.txt').write_text(content,encoding='utf-8')
print(json.dumps({'pages':11,'bytes':OUT.stat().st_size,'output':str(OUT)},ensure_ascii=False))
