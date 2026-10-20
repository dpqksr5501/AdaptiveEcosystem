// v3 사슴 두뇌 바꾸기 — 실행 중 가중치 로더 (10-18 사용자 '우리가 계획한 가중치 로더 써서 두뇌 바꿔주는 기술을 한번 적용해보자',
// 사람 결정 10-07 (3) '이식 때 함께 만든다', 계획서 Docs/RL_Policy/RL_SEASON_RETRAIN_PLAN.md 4.4.2 (나)·RL_V3_UNREAL_TRAINING_PLAN.md 4-5b).
//
// 무엇을 하나:
//   파이썬(herbivore_rl/export_weights_v3.py --brain-file)이 쓴 두뇌 파일(JSON)을 읽어 검사하고, 통과하면 Play 를 다시 시작하지 않고
//   통합 v3 모드의 사슴 두뇌(관측 18 또는 21 → 64 → 64 → 로짓 5, EcoPolicyV3Inference.h 의 같은 순전파)를 바꾼다. 내장 두뇌(PolicyWeightsV3.h,
//   R1b s3 — 통합 모드는 얼기를 세계가 막아 R1b-F)는 늘 남아 있고 'builtin' 으로 언제든 돌아간다. 추론은 그대로 C++ 이고 파이썬은 게임 안에서
//   돌지 않는다 — 바뀌는 것은 가중치의 출처뿐이다 (AGENTS.md 2절 4항).
//
// 안전 지점 (계약):
//   바꾸기는 줄(Queue)에 넣고, 통합 처리기가 결정 스텝 사이(전역 스텝 경계 — UEcoPolicyV3IntegratedSubsystem::SyncBrain)에서만 꺼내 쓴다.
//   사슴의 몸·행동 상태·기억·은신처 목표는 그대로다. 경계 스텝은 앞 두뇌가 그 앞 스텝 끝에 정한 요청을 실행하고, 그 스텝 끝 결정부터 새 두뇌다.
//   허용 칸 = 새 두뇌의 허용 칸 ∧ 세계 칸(eco.IntegratedV3.NoFreeze 등)으로 다시 정한다 (EcoWorldV3::SetModelAllowed).
//   서버·단독만 (처리기가 Server|Standalone). 클라이언트 콘솔의 명령은 거부한다. 저장소는 프로세스에 하나다(PIE 창 여럿이면 함께 바뀐다).
//   개발 빌드 전용: Shipping 에서는 콘솔 명령·변수가 없고 늘 내장 두뇌다 (RL_SEASON_RETRAIN_PLAN.md 9절 #S1 — 팀 합의 안건).
//
// 두뇌 파일 검사 (하나라도 어긋나면 거부, 지금 두뇌를 그대로 둔다 — EcoV3Brain::EReject):
//   형식·판 → 계약 해시 = 이 빌드가 관측을 만들 수 있는 계약 둘 중 하나 (EcoV3Brain::FindContract) → 차원(관측 = 그 계약의 칸 수·은닉 64·행동 5) →
//   관측·행동 이름 순서 → 마스크 판 → 마스크 문턱(float 비트) → 허용 칸(먹기 필수, 이름·칸 일치) → 층 모양 → base64 길이 → NaN·Inf →
//   가중치 바이트 sha256 → 골든 자체 확인(파일 속 관측 + 마스크를 RunPolicyV3 로 다시 돌려 로짓 |C++ − 파이썬| ≤ 허용 오차(≤ 1e-3), 행동은 같아야 한다, 8 사례 이상).
// 받는 계약 (10-19 R5 장애물 관측, 계약 POLICY_CONTRACT_V3.md 2-4):
//   관측 18 · 마스크 판 2  0x7eea0107339be4ce  내장 R1b 와 같은 계약 (빌드의 kContractHash)
//   관측 21 · 마스크 판 2  0xbc4fc2d45c47c5fd  18 칸 + escape_room·obstacle_near·threat_hidden. 통합 모드가 두뇌를 바꾸면 세계가 세 칸을 더 만든다
//                                              (EcoWorldV3::SetModelObsDim — 망 입력 = 관측 18 + 세 칸)
//   그 밖(예: R2 관측 19·판 3)은 '계약 해시' 로 거부한다 — C++ 관측 코드를 함께 바꿔야 한다.
//
// 콘솔 (개발 빌드):
//   eco.V3Brain.Load <파일|builtin>   파일 = 절대 경로, 또는 찾는 폴더(<프로젝트>/EcoBrains, <프로젝트>/Saved/EcoBrains) 안의 이름(.json 빼도 됨)
//   eco.V3Brain.Info                  지금 두뇌·대기 중 두뇌·바꾼 횟수·출처·검사 결과
//   eco.V3Brain.List                  찾는 폴더의 두뇌 파일과 검사 결과
//   eco.V3Brain.Startup <파일>        통합 v3 Play 를 시작할 때 불러올 두뇌 (빈 값 = 지금 두뇌 그대로, 처음은 내장). 명령줄 -EcoV3Brain=
//   eco.V3Brain.SwapAtSeconds <초>    예정 바꾸기 (측정·시연용, -1 = 끔): 시뮬레이션 시각(기록 줄의 초)이 되는 결정 스텝 경계에서 SwapFile 로.
//   eco.V3Brain.SwapFile <파일>         명령줄 -EcoV3BrainSwapAt= -EcoV3BrainSwapTo=
//   eco.V3Brain.WatchFolder <폴더>    폴더 감시 (기본 빈 값 = 끔): 2 초마다 폴더의 가장 새 *.json 이 바뀌면 불러와 다음 경계에서 바꾼다.
//                                      거부한 파일은 시각이 바뀔 때까지 다시 읽지 않는다. 명령줄 -EcoV3BrainWatch=
//                                      다만 JSON·풀기·읽기에서 깨진 파일이 3 초보다 새면 쓰는 중으로 보고 기억하지 않는다 (다음 감시에 다시 읽는다).
//   eco.V3Brain.Rollback              앞 두뇌로 되돌리기 (10-21 실시간 두뇌 교체): 되돌리기 쌓개(앞 두뇌 16 개)의 맨 위를 줄에 넣는다 — 다음 경계에서 바뀐다.
//                                      되돌린 두뇌는 쌓개에 다시 넣지 않는다 (두 번 누르면 둘 앞으로).
//   eco.V3Brain.History               되돌리기 쌓개 (새 것부터, 들어온 까닭·바뀐 까닭)
//   eco.V3Brain.Notice <0|1>          화면 알림 (기본 1, eco.V3Debug 와 따로 — 통합 서브시스템이 그린다. 기록 '[EcoV3I] 알림 |' 은 늘 남긴다)
//   eco.V3Brain.NoticeShot <0|1>      바꾸기·되돌리기 알림 1.5 초 뒤 화면 찍기 (기본 0, 시연 증거 — 그릴 수 없는 실행은 건너뛴다)
//   eco.V3Brain.StatusFile <파일>     적응 고리 상태 파일 (파이썬 live.py 가 쓴다 — eco_v3_live_status 판 1). 빈 값 = 끔, eco.IntegratedV3.AutoAdapt 면
//                                      Saved/EcoAdapt/status.json. 2 초마다 읽는다 (FEcoV3LiveStatus)
//
// 적응 고리 (10-21 사용자 '게임 중 실시간 두뇌 교체', 설계 LIVE_ADAPT_SPEC.md 5.4): 두뇌 파일의 'adapt' 블록(판·시도·실행·스냅숏·환경·관문)을 선택으로
//   읽는다 (없으면 판 0 = 없음, 깨진 값도 거부하지 않는다). 통합 모드가 eco.IntegratedV3.AutoAdapt 로 켜면 감시 폴더 기본 = Saved/EcoAdapt/brains
//   (eco.V3Brain.WatchFolder 가 비었을 때만), Play 시작 때 PrimeWatch — 그때 있던 파일은 (뒤에 다시 가장 새 파일이 돼도) 읽지 않고 뒤에 나타난 파일만 바꾼다.
//
// 기록: 바꿀 때마다 '[EcoV3I] 두뇌 바꿈 |' 한 줄(시각·전역 스텝·앞 → 새 두뇌 id·까닭·허용 칸), 10 초마다 지역마다 '[EcoV3I] <지역> 두뇌 |'
//   (지금 두뇌 id, 구간 두뇌 스텝(도주 반사 밖)의 행동 몫, 그중 늑대를 앎(관측 pred_count > 0)의 행동 몫 — R4 situ_eval.py 와 같은 정의).
// 두뇌 id = <모델 이름>@<가중치 sha256 앞 8자리>. 내장 두뇌와 같은 가중치의 파일은 id 가 같다.

#pragma once

#include "CoreMinimal.h"
#include "Misc/DateTime.h"
#include "Templates/SharedPointer.h"

#include "EcoPolicyV3Inference.h"

DECLARE_LOG_CATEGORY_EXTERN(LogEcoV3Brain, Log, All);

struct FEcoV3LiveStatus;

namespace EcoV3Brain
{
	inline constexpr const TCHAR* kFormat = TEXT("eco_v3_brain");
	inline constexpr int32 kFormatVersion = 1;
	inline constexpr float kMaxLogitTolerance = 1e-3f;   // 파일이 적은 허용 오차의 상한 (파이썬 기본 1e-4)
	inline constexpr int32 kMinGolden = 8;               // 골든 사례 하한
	inline constexpr double kWatchPollSeconds = 2.0;     // 폴더 감시 주기 (실시간)
	inline constexpr double kWatchYoungSeconds = 3.0;    // 폴더 감시: 이보다 새 파일이 읽기·JSON·풀기에서 깨졌으면 쓰는 중으로 보고 기억하지 않는다
	inline constexpr int32 kHistoryMax = 16;             // 되돌리기 쌓개 상한 (앞 두뇌 수 — 넘으면 가장 오래된 것을 버린다)
	inline constexpr const TCHAR* kLiveStatusFormat = TEXT("eco_v3_live_status");   // 적응 고리 상태 파일 형식 (LIVE_ADAPT_SPEC.md 4절)
	inline constexpr int32 kLiveStatusVersion = 1;
	inline constexpr double kStatusPollSeconds = 2.0;    // 상태 파일 읽기 주기 (실시간)
	inline constexpr double kStatusFreshSeconds = 120.0; // updated_unix 가 이 안이면 '적응 고리 | <message>', 넘으면 '응답 없음'

	/** 거부 까닭. */
	enum class EReject : uint8
	{
		None,
		File,         // 파일을 찾거나 읽지 못함
		Json,         // JSON 이 아님
		Format,       // 형식 이름·판·모델 이름
		Contract,     // 계약 해시가 이 빌드와 다름 (관측·마스크 계약이 다른 모델)
		Dims,         // 관측·은닉·행동 칸 수
		Names,        // 관측·행동 이름 순서
		Mask,         // 마스크 판
		Thresholds,   // 마스크 문턱·막힌 칸 로짓
		Allowed,      // 허용 칸
		Shape,        // 층 수·모양
		Decode,       // base64 가 깨졌거나 길이가 모양과 다름
		NonFinite,    // 가중치에 NaN·Inf
		Digest,       // 가중치 바이트 sha256 이 파일에 적힌 값과 다름
		Golden,       // 골든 자체 확인 실패 (로짓 오차·행동·사례 수·허용 오차)
		Play          // (폴더 감시만) 적응 고리 두뇌가 다른 Play 의 스냅숏에서 배운 것 — 파일은 멀쩡하다 (FEcoV3Brain::AdaptPlayId)
	};

	ADAPTIVEECOSYSTEM_API const TCHAR* RejectName(EReject Reason);

	/** 이 빌드가 관측을 만들 수 있는 입출력 계약 하나 (관측 이름 = 관측 18 이름 뒤에 Extra 이름). */
	struct FContract
	{
		uint64 Hash = 0;
		int32 ObsDim = 0;
		int32 MaskVersion = 0;
		int32 NumExtra = 0;                    // 관측 18 뒤 칸 수 (0 또는 3)
		const char* const* ExtraNames = nullptr;
		const TCHAR* Label = TEXT("");
	};

	/** 받는 계약 수 (관측 18 · 판 2, 관측 21 · 판 2). */
	inline constexpr int32 kNumContracts = 2;
	ADAPTIVEECOSYSTEM_API const FContract& Contract(int32 Index);
	/** 계약 해시 → 받는 계약 (없으면 nullptr). */
	ADAPTIVEECOSYSTEM_API const FContract* FindContract(uint64 Hash);
	/** 계약의 관측 칸 i 이름 (UTF-8). */
	ADAPTIVEECOSYSTEM_API const char* ContractObsName(const FContract& C, int32 i);

	/** 망 가중치 바이트(W0, B0, W1, B1, W2, B2 순서, float32 리틀 엔디언)의 sha256 16진 — 파이썬 export_weights_v3.weights_bytes 와 같은 바이트. */
	ADAPTIVEECOSYSTEM_API FString WeightsSha256(const EcoPolicyV3::FPolicyNetV3& Net);

	/** 행동 칸 → '먹기·도망·숨기' (켜진 칸만). */
	ADAPTIVEECOSYSTEM_API FString AllowedText(const uint8 Allowed[EcoPolicyV3::kNumBehaviors]);

	// 콘솔 변수 (개발 빌드. Shipping 은 빈 값·끔)
	ADAPTIVEECOSYSTEM_API FString StartupFile();
	ADAPTIVEECOSYSTEM_API float SwapAtSeconds();
	ADAPTIVEECOSYSTEM_API FString SwapFile();
	ADAPTIVEECOSYSTEM_API FString WatchFolder();
	ADAPTIVEECOSYSTEM_API bool NoticeEnabled();    // eco.V3Brain.Notice (기본 1)
	ADAPTIVEECOSYSTEM_API bool NoticeShot();       // eco.V3Brain.NoticeShot (기본 0)
	ADAPTIVEECOSYSTEM_API FString StatusFile();    // eco.V3Brain.StatusFile (기본 빈 값)

	/**
	 * 상태 파일 글자(eco_v3_live_status 판 1, LIVE_ADAPT_SPEC.md 4절) → Out. 형식·판이 다르거나 JSON 이 아니면 거짓 (Out 그대로, OutError = 까닭).
	 * 다른 칸은 선택이다 (없으면 기본값 — progress -1).
	 */
	ADAPTIVEECOSYSTEM_API bool ParseLiveStatus(const FString& JsonText, FEcoV3LiveStatus& Out, FString* OutError = nullptr);
	/**
	 * 화면 글자: 파일 없음 '적응 고리 | 파이썬 감시 없음', 읽지 못함 '적응 고리 | 상태 파일을 못 읽음', updated_unix 가 120 초 안 '적응 고리 | <message>'
	 * (message 가 비면 state), 넘으면 '적응 고리 | 응답 없음 (<n>초 전)'. NowUnix = 지금 유닉스 초 (NowUnixSeconds).
	 */
	ADAPTIVEECOSYSTEM_API FString LiveStatusText(const FEcoV3LiveStatus& Status, bool bFileExists, double NowUnix);
	/** 지금 유닉스 초 (UTC, 소수 — 파이썬 time.time() 과 같은 눈금). */
	ADAPTIVEECOSYSTEM_API double NowUnixSeconds();
}

/** 두뇌 하나 (가중치를 쥔다). Net 은 자기 배열을 가리키므로 복사하지 않는다 — TSharedRef 로만 다룬다. */
struct ADAPTIVEECOSYSTEM_API FEcoV3Brain
{
	FEcoV3Brain() = default;
	FEcoV3Brain(const FEcoV3Brain&) = delete;
	FEcoV3Brain& operator=(const FEcoV3Brain&) = delete;

	FString Id;              // <모델 이름>@<가중치 sha256 앞 8자리>
	FString ModelName;       // 모델 zip 이름 (확장자 없이)
	FString ModelPath;       // 파이썬이 적은 모델 경로 (herbivore_rl/ 기준)
	FString ModelSha256;     // 모델 zip sha256 (출처 기록 — 언리얼은 zip 을 보지 않는다)
	FString WeightsSha256;   // 가중치 바이트 sha256 (검사함)
	FString TrainConfig;     // 학습 설정 (모델 옆 학습 기록)
	FString TrainDigest;
	FString TrainWorld;      // 사람이 읽을 학습 세계 이름
	FString GoldenWorld;     // 골든을 뽑은 세계 설정
	FString SourceFile;      // 불러온 파일 (내장이면 빈 값)
	bool bBuiltin = false;
	uint64 ContractHash = 0; // 입출력 계약 해시 (내장 = kContractHash)
	int32 ObsDim = 0;        // 관측 칸 수 = Net.ObsDim (18 또는 21)
	uint8 Allowed[EcoPolicyV3::kNumBehaviors] = {};   // 모델 허용 칸 (실제 허용 = 이 칸 ∧ 세계 칸)
	int32 GoldenCount = 0;
	float GoldenTolerance = 0.0f;
	float GoldenMaxError = 0.0f;

	// 적응 고리 'adapt' 블록 (선택 — 없거나 깨졌으면 비어 있다. 거부하지 않는다, LIVE_ADAPT_SPEC.md 3절)
	bool bAdapt = false;     // 파일에 'adapt' 객체가 있었다 (스냅숏 brain.adapt 를 쓴다)
	int32 AdaptRound = 0;    // 받아들인 판 번호 1.. (0 = 없음 — 내장·손으로 만든 파일)
	int32 AdaptAttempt = 0;  // 시도 번호 (기각 포함)
	FString AdaptRun;        // 실행 이름 (live_<시각>_e<환경 판>)
	FString AdaptSnapshot;   // 바탕 스냅숏 파일 이름
	FString AdaptEnv;        // Play 시작 대비 바뀐 환경 (짧은 한국어)
	FString AdaptGate;       // 관문 결과 (짧은 한국어)
	FString AdaptPlayId;     // 바탕 스냅숏의 Play 번호 (play_id — 감시가 지금 Play 와 맞춰 본다. 비면 보지 않는다)

	// 파일 두뇌의 가중치 (내장 두뇌는 비어 있고 Net 이 PolicyWeightsV3.h 를 가리킨다). (out, in) 순서 — EcoPolicyV3Inference.h 와 같다
	TArray<float> Layer0Weight;
	TArray<float> Layer0Bias;
	TArray<float> Layer1Weight;
	TArray<float> Layer1Bias;
	TArray<float> Layer2Weight;
	TArray<float> Layer2Bias;
	EcoPolicyV3::FPolicyNetV3 Net = EcoPolicyV3::kBuiltinNet;

	/**
	 * 한 줄 요약: 'v3_r4_g995_s0_20m@f807bea5 (파일 v3_r4_g995_s0_20m.json, 허용 먹기·도망·숨기)'. 관측 21 두뇌는 '…, 관측 21 장애물)' 을,
	 * 'adapt' 판이 있으면 '…, 판 3)' 을 붙인다.
	 */
	FString Describe() const;
	/** 판 글자: 'adapt' 판이 있으면 '판 3', 내장이면 '판 0', 그 밖(손으로 만든 파일)은 빈 값. */
	FString RoundTag() const;
	/** 화면용 짧은 id: 'live_r3…@abcd' (모델 이름 10 자 넘으면 7 자 + '…' — live_r<판> 이름은 판 번호 끝까지 'live_r12…', 지문 앞 4 자). */
	FString ShortId() const;
};

using FEcoV3BrainRef = TSharedRef<const FEcoV3Brain, ESPMode::ThreadSafe>;
using FEcoV3BrainPtr = TSharedPtr<const FEcoV3Brain, ESPMode::ThreadSafe>;

/** 불러오기 결과. */
struct ADAPTIVEECOSYSTEM_API FEcoV3BrainLoad
{
	EcoV3Brain::EReject Reason = EcoV3Brain::EReject::None;
	FString Message;
	FString Path;            // 찾은 파일 (못 찾았으면 찾아본 경로들)
	FEcoV3BrainPtr Brain;

	bool Ok() const { return Reason == EcoV3Brain::EReject::None && Brain.IsValid(); }
};

/** 되돌리기 쌓개 한 칸 (앞 두뇌). */
struct FEcoV3BrainHistoryEntry
{
	FEcoV3BrainRef Brain;
	FString Why;           // 그 두뇌가 지금 두뇌가 된 까닭
	FString ReplacedWhy;   // 그 두뇌를 바꾼 까닭
};

/** 폴더 감시가 마지막으로 거부한 파일 (통합 서브시스템이 Serial 이 바뀔 때 한 번 알린다). */
struct FEcoV3WatchReject
{
	FString File;          // 거부한 파일 경로
	EcoV3Brain::EReject Reason = EcoV3Brain::EReject::None;
	FString Message;
	uint32 Serial = 0;     // 거부마다 + 1 (0 = 아직 없음. ResetForTest 도 되돌리지 않는다 — 알린 번호와 겹치지 않게)
};

/** 적응 고리 상태 (파이썬 live.py 가 쓰는 status.json, LIVE_ADAPT_SPEC.md 4절). 읽기·화면 전용. */
struct FEcoV3LiveStatus
{
	bool bValid = false;       // 형식·판을 읽었다
	FString Path;              // 읽은 파일
	FString State;             // idle·waiting·converting·checking·training·evaluating·gating·exporting·exported·rejected·refused·superseded·error
	FString Message;           // 화면 한 줄 (짧은 한국어)
	FString LastResult;        // 지난 시도 결과
	FString Snapshot;          // 다루는 스냅숏
	FString Env;               // 바뀐 환경 요약
	int32 Attempt = 0;         // 시도 번호
	int32 Round = 0;           // 마지막으로 받아들인 판
	int32 Pid = 0;
	double UpdatedUnix = 0.0;  // 파이썬이 고친 유닉스 초
	double Progress = -1.0;    // 0..1, 모르면 -1
};

/**
 * 두뇌 저장소 (프로세스에 하나, 게임 스레드에서만). 지금 두뇌(Active)와 다음 경계에서 바꿀 두뇌(Pending)를 쥔다.
 * 통합 처리기는 결정 스텝 경계마다 CommitPending 을 부르고(UEcoPolicyV3IntegratedSubsystem::SyncBrain), 바뀌면 세대 번호가 오른다.
 */
class ADAPTIVEECOSYSTEM_API FEcoV3BrainRegistry
{
public:
	static FEcoV3BrainRegistry& Get();

	/** 내장 두뇌 (PolicyWeightsV3.h). 늘 같은 객체다. */
	static FEcoV3BrainRef Builtin();

	/** 두뇌 파일 글자 → 검사 → 두뇌. Source = 기록에 적을 출처(파일 경로). */
	static FEcoV3BrainLoad Parse(const FString& JsonText, const FString& Source);
	/** 파일 이름·경로 → 찾기(Resolve) → 읽기 → Parse. 'builtin'·'내장' 은 내장 두뇌. */
	static FEcoV3BrainLoad LoadFile(const FString& PathOrName);
	/** 절대 경로면 그대로, 아니면 찾는 폴더마다 (이름, 이름.json). 못 찾으면 빈 값 (OutTried = 찾아본 경로들). */
	static FString Resolve(const FString& PathOrName, FString* OutTried = nullptr);
	/** 찾는 폴더: <프로젝트>/EcoBrains (저장소에 올린 두뇌), <프로젝트>/Saved/EcoBrains (내 실험 — git 밖). */
	static TArray<FString> SearchFolders();
	/** 찾는 폴더의 *.json (폴더 순, 이름 순). */
	static TArray<FString> ListFiles();
	static bool IsBuiltinName(const FString& Name);

	FEcoV3BrainRef GetActive() const { return Active; }
	FEcoV3BrainPtr GetPending() const { return Pending; }
	const FString& GetPendingWhy() const { return PendingWhy; }
	/** 지금 두뇌가 된 까닭 (처음 '내장 (처음)'). */
	const FString& GetActiveWhy() const { return ActiveWhy; }
	/** 바뀔 때마다 1 씩 오른다 (처음 1). */
	uint32 GetGeneration() const { return Generation; }
	int32 GetSwapCount() const { return SwapCount; }

	/**
	 * 다음 결정 스텝 경계에서 바꿀 두뇌를 줄에 넣는다 (먼저 넣은 대기 두뇌는 버린다 — 대기 되돌림이면 그 되돌리기들이 꺼낸 칸을 모두 쌓개에 돌려놓는다:
	 * 경계 전에 두 번 되돌렸어도 되돌리기를 부르기 전 쌓개 그대로). Why = 기록에 적을 까닭.
	 */
	void Queue(const FEcoV3BrainRef& Brain, const FString& Why);
	/**
	 * 대기 두뇌가 있으면 지금 두뇌로 바꾼다 (결정 스텝 경계에서만 부른다). 바꿨으면 참 (OutFrom = 앞 두뇌, OutWhy = 까닭, bOutRollback = 되돌림이었나).
	 * 되돌림이 아니면 나가는 두뇌를 되돌리기 쌓개에 쌓는다 (같은 id 로 바꾸면 쌓지 않는다, 많아야 kHistoryMax — 넘으면 가장 오래된 것을 버린다).
	 */
	bool CommitPending(FEcoV3BrainPtr* OutFrom = nullptr, FString* OutWhy = nullptr, bool* bOutRollback = nullptr);
	/**
	 * 되돌리기 (eco.V3Brain.Rollback): 쌓개 맨 위 두뇌를 되돌림으로 줄에 넣는다 — 다음 결정 스텝 경계에서 바뀌고, 나가는 두뇌는 쌓지 않는다.
	 * 이미 대기 되돌림이 있으면 그 두뇌를 건너뛰고 하나 더 앞으로 (건너뛴 칸은 경계에서 되돌림이 바뀌면 버리고, 다른 두뇌가 줄을 덮으면 돌려놓는다).
	 * 쌓개가 비었으면 거짓 (OutMessage = 까닭). Why = 기록에 적을 까닭.
	 */
	bool Rollback(const FString& Why, FString* OutMessage = nullptr);
	/** 되돌리기 쌓개 (오래된 것부터 — 맨 끝이 다음 되돌림). */
	const TArray<FEcoV3BrainHistoryEntry>& GetHistory() const { return History; }
	/** 대기 두뇌가 되돌림인가. */
	bool IsPendingRollback() const { return !PendingRollback.IsEmpty(); }
	/** 마지막 CommitPending 이 되돌림이었나·그 까닭 (저장소는 프로세스에 하나라 다른 월드가 바꾼 것도 여기서 본다). */
	bool WasLastCommitRollback() const { return bLastCommitRollback; }
	const FString& GetLastCommitWhy() const { return LastCommitWhy; }

	/**
	 * 폴더 감시 (EffectiveWatchFolder). NowSeconds = 실시간. 새 파일을 줄에 넣었으면 참. 가장 새 파일 하나만 본다. 거부하면 GetLastWatchReject 를 고친다
	 * (Serial + 1). 읽기·JSON·풀기에서 깨진 파일이 kWatchYoungSeconds 보다 새면 거부로 치지 않고 기억하지 않는다 (다음 감시에 다시 읽는다).
	 */
	bool PollWatch(double NowSeconds);
	/**
	 * 감시 준비 (적응 고리 — Play 시작 때): 지금 폴더의 *.json 모두(경로·시각)를 읽지 않고 기억한다. 그 뒤에 나타나거나 바뀐 파일만 줄에 넣는다
	 * (더 새 파일이 지워져 그때 있던 파일이 다시 가장 새 파일이 돼도 읽지 않는다). ClearWatchPrime·다음 PrimeWatch·ResetForTest 까지.
	 */
	void PrimeWatch();
	/** PrimeWatch 기억을 지운다 (통합 서브시스템이 적응 고리 Play 가 끝날 때 — 다음 Play 의 손 감시 폴더는 예전처럼 가장 새 파일을 읽는다). */
	void ClearWatchPrime();
	/** 감시 폴더 = eco.V3Brain.WatchFolder, 비면 SetDefaultWatchFolder 값 (Shipping 은 늘 빈 값). 상대 경로는 그대로 (PollWatch 가 프로젝트 기준으로 푼다). */
	FString EffectiveWatchFolder() const;
	/** 적응 고리 기본 감시 폴더 (통합 서브시스템이 eco.IntegratedV3.AutoAdapt 면 Play 시작 때 정하고 끝날 때 지운다). */
	void SetDefaultWatchFolder(const FString& Folder) { DefaultWatchFolder = Folder; }
	/**
	 * 지금 Play 번호 (통합 서브시스템이 적응 고리 Play 시작 때 정하고 끝날 때 지운다 — 스냅숏 play_id). 비지 않으면 감시는 adapt.play_id 가 있고 이것과 다른
	 * 두뇌를 받지 않는다 (앞 Play 에서 시작한 파이썬 판이 새 Play 가 시작된 뒤에 끝난 경우 — 그 두뇌는 앞 Play 의 환경에서 배웠다).
	 */
	void SetWatchPlayId(const FString& Id) { WatchPlayId = Id; }
	const FString& GetWatchPlayId() const { return WatchPlayId; }
	const FEcoV3WatchReject& GetLastWatchReject() const { return LastWatchReject; }

	/**
	 * 상태 파일 읽기 (EffectiveStatusFile, kStatusPollSeconds 마다 — 실시간). 읽어 봤으면 참. 파일이 없으면 상태를 비우고, 형식이 깨졌으면
	 * 앞서 읽은 상태를 그대로 둔다 (파이썬은 바꿔 끼우기로 쓴다).
	 */
	bool PollStatus(double NowSeconds);
	/** 상태 파일 = eco.V3Brain.StatusFile, 비면 SetDefaultStatusFile 값 (Shipping 은 늘 빈 값). */
	FString EffectiveStatusFile() const;
	void SetDefaultStatusFile(const FString& Path) { DefaultStatusFile = Path; }
	const FEcoV3LiveStatus& GetLiveStatus() const { return LiveStatus; }
	/** 화면 글자 (EcoV3Brain::LiveStatusText). 상태 파일이 꺼졌거나 아직 읽지 않았으면 빈 값. */
	FString GetLiveStatusText(double NowUnix) const;

	/** 시험 전용: 내장 두뇌로 곧바로 되돌리고 대기·감시·쌓개·상태 파일·기본 폴더를 지운다 (거부 Serial 은 되돌리지 않는다). */
	void ResetForTest();

private:
	FEcoV3BrainRegistry();

	/** Queue 와 Rollback 이 함께 쓴다 (RollbackEntry 가 있으면 되돌림 — 대기 되돌림 칸들 뒤에 붙인다. 없으면 대기 되돌림 칸들을 쌓개에 돌려놓는다). */
	void QueueImpl(const FEcoV3BrainRef& Brain, const FString& Why, TOptional<FEcoV3BrainHistoryEntry> RollbackEntry);

	FEcoV3BrainRef Active;
	FString ActiveWhy;
	FEcoV3BrainPtr Pending;
	FString PendingWhy;
	TArray<FEcoV3BrainHistoryEntry> PendingRollback;      // 대기 두뇌가 되돌림이면 쌓개에서 꺼낸 칸들 (꺼낸 순, 맨 끝 = 대기 두뇌 — 다른 두뇌가 줄을 덮으면 모두 돌려놓는다)
	TArray<FEcoV3BrainHistoryEntry> History;               // 되돌리기 쌓개 (오래된 것부터)
	uint32 Generation = 1;
	int32 SwapCount = 0;
	bool bLastCommitRollback = false;
	FString LastCommitWhy;

	FString WatchedFile;
	FDateTime WatchedStamp;
	double NextWatchPoll = 0.0;
	TMap<FString, FDateTime> PrimedFiles;   // PrimeWatch 때 있던 파일 (경로 → 시각) — 같은 (경로, 시각) 은 읽지 않는다
	FString DefaultWatchFolder;
	FString WatchPlayId;
	FEcoV3WatchReject LastWatchReject;

	FString DefaultStatusFile;
	FString StatusPath;           // 마지막으로 읽어 본 상태 파일 (절대 경로, 빈 값 = 아직)
	double NextStatusPoll = 0.0;
	bool bStatusFileExists = false;
	bool bStatusReadOk = false;
	FEcoV3LiveStatus LiveStatus;
};
