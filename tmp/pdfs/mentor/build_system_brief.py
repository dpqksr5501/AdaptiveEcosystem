from pathlib import Path
from math import atan2, cos, sin, pi
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from PIL import Image
from pypdf import PdfReader
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
PDF = OUT / 'AdaptiveEcosystem_시스템설명_멘토검토용.pdf'
pdfmetrics.registerFont(TTFont('Korean', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KoreanBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Korean', normal='Korean', bold='KoreanBold')
W,H = A4
M=42; CW=W-2*M
NAVY='#172D3A'; TEAL='#087E82'; INK='#233B47'; MUTED='#5B707B'
PALE='#EFF5F5'; LINE='#D7E3E5'; AMBER='#966A18'; SAND='#FAF2DF'
C=canvas.Canvas(str(PDF),pagesize=A4,pageCompression=1)
C.setTitle('AdaptiveEcosystem | 우리가 만들고 싶은 동적 생태계')
C.setAuthor('AdaptiveEcosystem Team')
C.setSubject('멘토 검토용 시스템 설명: 목표 설계와 현재 통합 범위')
layout=[]

def rect(x,y,w,h,fill=PALE,stroke=None,r=9):
    C.setFillColor(colors.HexColor(fill)); C.setStrokeColor(colors.HexColor(stroke or fill))
    C.roundRect(x,H-y-h,w,h,r,fill=1,stroke=bool(stroke))

def txt(x,y,s,size=11,color=INK,bold=False):
    C.setFillColor(colors.HexColor(color)); C.setFont('KoreanBold' if bold else 'Korean',size)
    C.drawString(x,H-y-size,s)
    if x+pdfmetrics.stringWidth(s,'KoreanBold' if bold else 'Korean',size)>W-M+1:
        raise ValueError(f'text overflow {s}')

def para(x,y,w,s,size=10.7,color=INK,bold=False,leading=None,maxh=None):
    st=ParagraphStyle('p',fontName='KoreanBold' if bold else 'Korean',fontSize=size,
        leading=leading or size*1.65,textColor=colors.HexColor(color),wordWrap='CJK')
    p=Paragraph(s,st);_,h=p.wrap(w,1000)
    if maxh is not None and h>maxh: raise ValueError(f'paragraph too tall {h}/{maxh}: {s}')
    if y+h>H-48: raise ValueError(f'page overflow: {s}')
    p.drawOn(C,x,H-y-h);layout.append({'page':C.getPageNumber(),'top':y,'height':h,'text':s})
    return h

def arrow(x1,y1,x2,y2,color=TEAL,dash=False):
    C.setStrokeColor(colors.HexColor(color));C.setFillColor(colors.HexColor(color));C.setLineWidth(1.6)
    C.setDash(4,3) if dash else C.setDash()
    C.line(x1,H-y1,x2,H-y2);C.setDash()
    a=atan2(y2-y1,x2-x1);p=C.beginPath();p.moveTo(x2,H-y2)
    p.lineTo(x2-7*cos(a-pi/7),H-(y2-7*sin(a-pi/7)))
    p.lineTo(x2-7*cos(a+pi/7),H-(y2-7*sin(a+pi/7)));p.close();C.drawPath(p,fill=1,stroke=0)

def pill(x,y,s,goal=False):
    w=pdfmetrics.stringWidth(s,'KoreanBold',9)+18
    rect(x,y,w,22,SAND if goal else '#E2F1EF',r=11)
    txt(x+9,y+4,s,9,AMBER if goal else TEAL,True)

def node(x,y,w,h,title,body,goal=False):
    rect(x,y,w,h,SAND if goal else PALE,LINE)
    txt(x+13,y+12,title,12,AMBER if goal else TEAL,True)
    para(x+13,y+35,w-26,body,9.6,maxh=h-40)

def photo(path,x,y,w,h,crop=None):
    im=Image.open(path);iw,ih=im.size
    C.saveState();p=C.beginPath();p.rect(x,H-y-h,w,h);C.clipPath(p,stroke=0,fill=0)
    if crop:
        left,top,right,bottom=crop;scale=min(w/(right-left),h/(bottom-top))
        ox=x+(w-(right-left)*scale)/2-left*scale
        oy=H-y-h+(h-(bottom-top)*scale)/2-(ih-bottom)*scale
    else:
        scale=min(w/iw,h/ih);ox=x+(w-iw*scale)/2;oy=H-y-h+(h-ih*scale)/2
    C.drawImage(str(path),ox,oy,width=iw*scale,height=ih*scale)
    C.restoreState()

def page(no,kicker,title,subtitle):
    C.setFillColor(colors.HexColor('#FCFDFD'));C.rect(0,0,W,H,fill=1,stroke=0)
    txt(M,24,'AdaptiveEcosystem',9,TEAL,True)
    txt(W-150,24,'멘토 검토용 · 2026.10.11',8.1,MUTED)
    txt(M,61,kicker,9,TEAL,True)
    txt(M,82,title,23,NAVY,True)
    para(M,122,CW,subtitle,10.6,MUTED,maxh=44)
    C.setStrokeColor(colors.HexColor(LINE));C.line(M,43,W-M,43)
    txt(M,H-32,'UE 5.8 · 목표 설계와 현재 통합 범위를 구분한 설명 자료',8,MUTED)
    txt(W-77,H-32,f'{no} / 7',8,MUTED)

def finish(): C.showPage()

initial=ROOT/'AdaptiveEcosystem/Saved/Screenshots/WindowsEditor/HighresScreenshot00004.png'
old=ROOT/'Deliverables/WeeklyReport_20261009/.build/previous'

# 1. Project vision, with a genuine early runtime capture.
page(1,'01 / 프로젝트 소개','우리가 만들고 싶은 동적 생태계',
     '환경이 동물의 행동을 바꾸고, 동물의 행동이 다시 환경과 개체군을 바꾸는 시스템입니다.')
rect(M,179,CW,103,NAVY)
para(M+19,196,CW-38,'“먹이가 줄면 이동하고, 위험이 커지면 무리와 숨고,<br/>그 결과가 다음 행동의 조건을 바꾸게 만들고 싶습니다.”',15,'#FFFFFF',True,maxh=68)
photo(initial,M,301,CW,225,crop=(160,210,1090,620))
para(M,534,CW,'그림 1. 실제 초기 평면 테스트의 사슴 표현 화면. 현재 3지역 레벨이나 최신 감각 검증 장면을 뜻하지 않습니다.',8.7,MUTED,maxh=34)
txt(M,587,'프로젝트를 이해하는 세 가지 키워드',13,NAVY,True)
for i,(t,b) in enumerate([
    ('동적 생태계','먹이·위험·개체군의 변화가 서로 영향을 주는 순환 구조'),
    ('학습된 행동','개체별 상황을 바탕으로 먹이 탐색·결집·도주·은신을 선택'),
    ('무리와 감각','시야·소리·기억을 해석하고 경보와 은신처로 대응')]):
    y=619+i*44;txt(M,y,t,11,TEAL,True);para(M+111,y,CW-111,b,10.2,maxh=36)
finish()

# 2. Closed-loop target, not a completed-runtime claim.
page(2,'02 / 핵심 목표','행동의 결과가 다음 판단으로 돌아옵니다',
     '아래는 전체 프로젝트의 목표 흐름입니다. 각 기능의 연결 여부는 마지막 페이지에서 따로 설명합니다.')
pill(M,173,'전체 폐루프: 목표 설계',True)
left=M;right=313;nw=240;nh=90
node(left,218,nw,nh,'1. 환경과 지역 자원','날씨·낮밤·지형 / 먹이 양·최근 포식 이력',True)
node(right,218,nw,nh,'2. 개체의 관측','주변 먹이와 위험, 동료, 에너지, 은신처 거리',True)
node(right,357,nw,nh,'3. 정책과 사회적 판단','PPO 행동 + 개인 감각·무리 경보 + 은신처 의도',True)
node(right,496,nw,nh,'4. 실제 이동과 상호작용','먹이 탐색·섭식·도주·대피·포식·지역 이동',True)
node(left,496,nw,nh,'5. 생태계 상태 갱신','자원 소비·재생 / 생존·사망 / 지역별 개체군 변화',True)
arrow(282,263,305,263,AMBER);arrow(433,311,433,348,AMBER)
arrow(433,450,433,487,AMBER);arrow(305,541,282,541,AMBER)
C.setStrokeColor(colors.HexColor(AMBER));C.setLineWidth(1.6)
C.line(42,H-541,30,H-541);C.line(30,H-541,30,H-263)
arrow(30,263,40,263,AMBER)
para(58,356,210,'행동 결과를 다시 반영<br/><b>FoodAmount · Population<br/>PredationHistory</b>',10.8,AMBER,maxh=80)
rect(M,622,CW,120)
txt(M+16,638,'예를 들어, 숲에서 먹이가 줄어든다면',12,TEAL,True)
para(M+16,666,CW-32,'먹이가 줄어듦 → 개체의 관측이 달라짐 → 탐색이나 지역 이동을 선택함 → 지역별 자원과 개체군이 달라짐 → 다음 판단에 다시 반영됩니다.<br/>이 순환이 실제 실행에서 이어지는 것이 최종 목표입니다.',10.7,maxh=65)
finish()

# 3. Habitats: readable schematic, with explicit illustration label.
page(3,'03 / 월드와 생태 상태','세 지역이 서로 다른 행동 조건을 제공합니다',
     '팀 레벨의 세 지역과 초기 동물 구성을 설명 그림으로 정리했습니다.')
pill(M,178,'3지역 구성: 설명용 도식')
regions=[('숲·초원','Forest','사슴 8 / 늑대 1','은신처 2곳 · 각 4슬롯','#E3F0E5'),
         ('황무지','Barren','사슴 4 / 늑대 1','숲과 고지대의 인접 지역','#F2E9D9'),
         ('고지대·설원','Highland','사슴 4 / 늑대 1','원본 지형과 물 영역 유지','#E5EDF5')]
for i,(t,en,count,detail,bg) in enumerate(regions):
    y=222+i*111;rect(M,y,CW,91,bg)
    txt(M+17,y+13,t,16,NAVY,True);txt(M+17,y+40,en,10,MUTED)
    txt(M+194,y+15,count,12,INK,True);txt(M+194,y+44,detail,10,INK)
    if i<2: arrow(M+CW/2,y+94,M+CW/2,y+106)
para(M,561,CW,'현재 통합 테스트의 초기 구성은 사슴 16마리·늑대 3마리입니다. 웨이브가 꺼져 있어 포식 이후 개체 수가 감소합니다. [2, 3]',10.2,MUTED,maxh=36)
txt(M,617,'환경 조건과 생태 상태의 역할을 나눕니다',13,NAVY,True)
para(M,649,CW,'<b>환경 계층</b>은 지형·지역 경계·날씨·낮밤 정보를 제공합니다.<br/><b>생태계 계층</b>은 지역 먹이 양, 포식 이력, 개체군을 관리합니다.<br/><b>목표 확장</b>은 지역 날씨와 식생·자원의 연결, 낮밤에 따른 행동 변화입니다. 물은 현재 진입 방지까지이며 갈증·마시기 행동은 후속 범위입니다.',10.7,maxh=112)
finish()

# 4. Shared policy, individual observations, offline Python.
page(4,'04 / 학습과 행동 결정','같은 모델을 사용해도 개체의 행동은 다릅니다',
     'PPO는 직접 좌표를 출력하는 대신 행동의 선호를 만듭니다. 각 동물의 관측이 다르면 출력도 달라집니다.')
txt(M,182,'관측 7개',13,TEAL,True)
labels=['먹이 밀도','포식자 수','포식자 거리','동종 개체 수','에너지','최근 포식 이력','은신처 거리']
for i,s in enumerate(labels):
    col=i%4;row=i//4;xx=M+col*130;yy=214+row*44
    rect(xx,yy,121,33);txt(xx+9,yy+9,s,10.1)
node(M,331,191,96,'개체별 관측','각자의 먹이·위험·에너지<br/>서로 다른 상황을 관측')
node(281,331,272,96,'공유 PPO 모델','신경망 7 → 64 → 64 → 4<br/>가중치는 공유, 관측과 출력은 개체별')
arrow(237,379,273,379)
arrow(416,430,416,458)
rect(M,467,CW,104,NAVY)
txt(M+17,481,'행동 4개',13,'#FFFFFF',True)
para(M+17,509,CW-34,'먹이 탐색(forage) · 무리 결집(cohesion)<br/>도주 민감도(flee_dist) · 은신처 선호(cover)',12,'#FFFFFF',maxh=44)
txt(M,607,'학습은 Python에서, 게임 실행은 Unreal C++에서',13,NAVY,True)
para(M,637,CW,'Python 학습 → 가중치 Export → C++ Native 추론으로 연결합니다. 게임 실행 중 Python 외부 추론을 기다리는 구조는 사용하지 않습니다.<br/>학습 환경과 게임의 관측 순서·정규화·행동 의미를 맞추고, 동일한 입력에 대한 출력 비교(Golden Vector)로 수치를 확인합니다. 현재 감각·포식 조건과 학습 시나리오의 차이는 추가 합의가 필요합니다. [4, 5]',10.6,maxh=122)
finish()

# 5. Social workflow plus honest historical screenshots.
page(5,'05 / 감각과 사회적 행동','위협을 인지하고, 무리와 안전한 곳을 찾습니다',
     '사슴은 위험을 공유하고 대피 의도를 만듭니다. 늑대는 직접 보거나 들은 먹잇감 단서를 추적합니다.')
steps=[('감각','시야·차폐·소리·기억'),('무리 경보','전파·감쇠·행동 보정'),('은신처','평가·슬롯 예약·목적지')]
for i,(t,b) in enumerate(steps):
    x=M+i*174;node(x,185,163,87,t,b)
    if i<2: arrow(x+165,229,x+171,229)
para(M,290,CW,'PPO 원본 행동은 보존하고, Social이 보정 행동과 은신처 목적지를 전달합니다. 기존 이동 계층은 이를 실행하고 도착·실패 결과를 반환합니다. [3]',10.8,maxh=54)
rect(M,353,CW,67,NAVY)
para(M+16,369,CW-32,'선택·예약 → 이동 중 → 도착·점유 → 필요 종료·실패·죽음 시 반환',11.8,'#FFFFFF',True,maxh=43)
photo(old/'p5_0_I1.png',M,442,247,146)
photo(old/'p6_0_I1.png',M+264,442,247,146)
para(M,598,247,'그림 2. 과거 무리·경보 디버그 화면.<br/>개체 상태와 무리 범위를 표시합니다.',8.7,MUTED,maxh=40)
para(M+264,598,247,'그림 3. 과거 차폐·은신처 예약 화면.<br/>최신 이동·점유 장면과는 구분합니다.',8.7,MUTED,maxh=40)
txt(M,660,'기억은 마지막으로 감지한 위치입니다',12,NAVY,True)
para(M,687,CW,'시야 밖 대상의 현재 좌표를 계속 아는 방식은 피합니다. 기억은 감쇠·만료되고, opt-in 늑대 포식에는 최근 직접 시야와 현재 LOS 확인이 필요합니다. 은신처 예약은 이동 및 점유와 구분하여 관리합니다. [3]',10.5,maxh=76)
finish()

# 6. Ownership and team integration.
page(6,'06 / 역할과 실행 구조','서버는 판단하고, 클라이언트는 표현합니다',
     '논리 상태와 화면 표현을 분리하고, 실제 이동을 갱신하는 경로는 개체별 하나로 유지합니다.')
node(M,182,CW,88,'서버 / Standalone: 논리 권위','지역 자원·개체군 / Mass 개체의 HP·에너지·위치 / 감각·무리 경보·은신처 예약')
arrow(M+CW/2,273,M+CW/2,302)
txt(M+CW/2+12,278,'이동 결과·지역 요약 전달',9,MUTED)
node(M,311,CW,88,'클라이언트: 전달받은 결과의 표현','Mass 복제 결과 → 동물 BP·Mesh·애니메이션·방향 정렬·로컬 발소리')
txt(M,433,'팀 시스템은 아래 경계에서 연결됩니다',13,NAVY,True)
rows=[('월드·레벨','지역 경계와 날씨·낮밤·지형 입력 제공'),
      ('생태계·Mass','자원, 개체 상태, 생명주기와 지역 집계 관리'),
      ('학습·정책','관측·보상·학습 모델과 원본 행동 생성'),
      ('Social·감각','개인 인지, 무리 경보, 보정 행동과 은신처 의도'),
      ('이동','의도 소비, 조향·위치 갱신, 도착·실패 반환'),
      ('네트워크·표현','결과 전달과 수신 상태의 화면·오디오 표현')]
for i,(a,b) in enumerate(rows):
    y=469+i*37;rect(M,y,CW,32,'#F0F5F5' if i%2==0 else '#FAFCFC',r=3)
    txt(M+10,y+8,a,10,TEAL,True);txt(M+137,y+8,b,9.8)
para(M,713,CW,'서버의 AI 소음은 실제 이동 거리로 생성하고, 클라이언트 발소리는 애니메이션 접촉에 맞춰 로컬 재생합니다. 두 이벤트는 프레임 단위로 동일하지 않습니다. [1, 3]',10.2,MUTED,maxh=50)
finish()

# 7. Scope, evidence and document-level references.
page(7,'07 / 현재 범위와 다음 연결','연결한 부분과 앞으로 확인할 부분',
     '2026.10.08 구현·검증 기록과 현재 체크아웃의 관련 Source를 대조해 요약했습니다. 이번 문서 제작에서 새 빌드나 PIE는 실행하지 않았습니다.')
pill(M,180,'현재 opt-in 동물 통합 경로')
para(M,215,CW,'• PPO → Social 보정·요청 → 기존 단일 이동 → 도착·실패 Feedback<br/>• 사슴 위협 감각·무리 경보·은신처 이동·점유·반환<br/>• 늑대 먹잇감 감각·기억, 동물 표현·Grass/Dry 발소리<br/>• 기존 기록: 직접 UBT 빌드, 자동화 43/43, PIE 및 서버/Client 재접속 확인',10.5,maxh=94)
pill(M,329,'추가 합의·연결·검증 필요',True)
para(M,364,CW,'• 감각·포식 조건을 Python 학습 시나리오와 맞추는 작업<br/>• 지역 날씨·식생·물 입력 연결과 시각/논리 낮밤의 동기화<br/>• 장애물 우회, 실제 플레이어 환경, 장시간·지연·대규모 운영 검증<br/>• 자원·섭식·에너지·사망·이주가 이어지는 전체 폐루프의 통합 평가',10.5,maxh=94)
rect(M,473,CW,58,SAND)
para(M+13,485,CW-26,'현재 opt-in 동물 경로의 검증을 기존 M3/JYU 전체 전환이나 모든 목표 기능의 완료로 확대하지 않습니다. 무리 병합·분할, ORCA, 자동 은신처 생성은 후속 검토 범위입니다.',9.5,AMBER,maxh=36)
txt(M,550,'자료와 그림의 출처',12,NAVY,True)
refs=[
    '[1] Docs/Architecture/PPO_MASS_ECOSYSTEM_ARCHITECTURE.md (전체 목표 설계)',
    '[2] Docs/조연우/ECOSYSTEM_LEVEL_RUNTIME_PLACEMENT.md (2026.10.08 배치 기록)',
    '[3] Docs/조연우/README.md 및 CREATURE_SENSORY_AND_NOTIFY_REFINEMENT.md',
    '[4] Docs/RL_Policy/POLICY_CONTRACT_V1.md (관측·행동 계약, 기존 수치 차이 명시)',
    '[5] herbivore_rl/docs/PROJECT_SUMMARY.md (실제 Python 학습 경로)',
    '그림 1: Saved/Screenshots/WindowsEditor/HighresScreenshot00004.png',
    '그림 2·3: 기존 진행 보고 자료의 실제 디버그 캡처 (과거 검증 장면)',
    '기타 도식: 저장소 문서에 근거해 새로 구성한 설명용 그림. 실제 레벨 사진 아님.'
]
yy=579
for s in refs:
    yy+=para(M,yy,CW,s,8.5,MUTED,leading=13.4,maxh=29)+6
finish()
C.save()
reader=PdfReader(PDF)
assert len(reader.pages)==7
text='\n'.join(p.extract_text() for p in reader.pages)
for term in ['동적 생태계','PPO','목표 설계','43/43','현재','클라이언트']:
    assert term in text,term
(ROOT/'tmp/pdfs/mentor/layout.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'tmp/pdfs/mentor/extracted.txt').write_text(text,encoding='utf-8')
print(json.dumps({'path':str(PDF),'pages':len(reader.pages),'bytes':PDF.stat().st_size},ensure_ascii=False))
