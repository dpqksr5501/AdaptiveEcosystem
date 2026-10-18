// v3 사슴 두뇌 바꾸기 — 실행 중 가중치 로더 (10-18 사용자 '우리가 계획한 가중치 로더 써서 두뇌 바꿔주는 기술을 한번 적용해보자',
// 사람 결정 10-07 (3) '이식 때 함께 만든다', 계획서 Docs/RL_Policy/RL_SEASON_RETRAIN_PLAN.md 4.4.2 (나)·RL_V3_UNREAL_TRAINING_PLAN.md 4-5b).
//
// 무엇을 하나:
//   파이썬(herbivore_rl/export_weights_v3.py --brain-file)이 쓴 두뇌 파일(JSON)을 읽어 검사하고, 통과하면 Play 를 다시 시작하지 않고
//   통합 v3 모드의 사슴 두뇌(관측 18 → 64 → 64 → 로짓 5, EcoPolicyV3Inference.h 의 같은 순전파)를 바꾼다. 내장 두뇌(PolicyWeightsV3.h,
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
//   형식·판 → 계약 해시 = 빌드의 kContractHash → 차원(관측 18·은닉 64·행동 5) → 관측·행동 이름 순서 → 마스크 판 → 마스크 문턱(float 비트) →
//   허용 칸(먹기 필수, 이름·칸 일치) → 층 모양 → base64 길이 → NaN·Inf → 가중치 바이트 sha256 → 골든 자체 확인(파일 속 관측 + 마스크를
//   RunPolicyV3 로 다시 돌려 로짓 |C++ − 파이썬| ≤ 허용 오차(≤ 1e-3), 행동은 같아야 한다, 8 사례 이상).
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

namespace EcoV3Brain
{
	inline constexpr const TCHAR* kFormat = TEXT("eco_v3_brain");
	inline constexpr int32 kFormatVersion = 1;
	inline constexpr float kMaxLogitTolerance = 1e-3f;   // 파일이 적은 허용 오차의 상한 (파이썬 기본 1e-4)
	inline constexpr int32 kMinGolden = 8;               // 골든 사례 하한
	inline constexpr double kWatchPollSeconds = 2.0;     // 폴더 감시 주기 (실시간)

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
		Golden        // 골든 자체 확인 실패 (로짓 오차·행동·사례 수·허용 오차)
	};

	ADAPTIVEECOSYSTEM_API const TCHAR* RejectName(EReject Reason);

	/** 망 가중치 바이트(W0, B0, W1, B1, W2, B2 순서, float32 리틀 엔디언)의 sha256 16진 — 파이썬 export_weights_v3.weights_bytes 와 같은 바이트. */
	ADAPTIVEECOSYSTEM_API FString WeightsSha256(const EcoPolicyV3::FPolicyNetV3& Net);

	/** 행동 칸 → '먹기·도망·숨기' (켜진 칸만). */
	ADAPTIVEECOSYSTEM_API FString AllowedText(const uint8 Allowed[EcoPolicyV3::kNumBehaviors]);

	// 콘솔 변수 (개발 빌드. Shipping 은 빈 값·끔)
	ADAPTIVEECOSYSTEM_API FString StartupFile();
	ADAPTIVEECOSYSTEM_API float SwapAtSeconds();
	ADAPTIVEECOSYSTEM_API FString SwapFile();
	ADAPTIVEECOSYSTEM_API FString WatchFolder();
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
	uint8 Allowed[EcoPolicyV3::kNumBehaviors] = {};   // 모델 허용 칸 (실제 허용 = 이 칸 ∧ 세계 칸)
	int32 GoldenCount = 0;
	float GoldenTolerance = 0.0f;
	float GoldenMaxError = 0.0f;

	// 파일 두뇌의 가중치 (내장 두뇌는 비어 있고 Net 이 PolicyWeightsV3.h 를 가리킨다). (out, in) 순서 — EcoPolicyV3Inference.h 와 같다
	TArray<float> Layer0Weight;
	TArray<float> Layer0Bias;
	TArray<float> Layer1Weight;
	TArray<float> Layer1Bias;
	TArray<float> Layer2Weight;
	TArray<float> Layer2Bias;
	EcoPolicyV3::FPolicyNetV3 Net = EcoPolicyV3::kBuiltinNet;

	/** 한 줄 요약: 'v3_r4_g995_s0_20m@f807bea5 (파일 v3_r4_g995_s0_20m.json, 허용 먹기·도망·숨기)'. */
	FString Describe() const;
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
	/** 바뀔 때마다 1 씩 오른다 (처음 1). */
	uint32 GetGeneration() const { return Generation; }
	int32 GetSwapCount() const { return SwapCount; }

	/** 다음 결정 스텝 경계에서 바꿀 두뇌를 줄에 넣는다 (먼저 넣은 대기 두뇌는 버린다). Why = 기록에 적을 까닭. */
	void Queue(const FEcoV3BrainRef& Brain, const FString& Why);
	/** 대기 두뇌가 있으면 지금 두뇌로 바꾼다 (결정 스텝 경계에서만 부른다). 바꿨으면 참 (OutFrom = 앞 두뇌, OutWhy = 까닭). */
	bool CommitPending(FEcoV3BrainPtr* OutFrom = nullptr, FString* OutWhy = nullptr);
	/** 폴더 감시 (eco.V3Brain.WatchFolder). NowSeconds = 실시간. 새 파일을 줄에 넣었으면 참. */
	bool PollWatch(double NowSeconds);
	/** 시험 전용: 내장 두뇌로 곧바로 되돌리고 대기·감시 상태를 지운다. */
	void ResetForTest();

private:
	FEcoV3BrainRegistry();

	FEcoV3BrainRef Active;
	FEcoV3BrainPtr Pending;
	FString PendingWhy;
	uint32 Generation = 1;
	int32 SwapCount = 0;

	FString WatchedFile;
	FDateTime WatchedStamp;
	double NextWatchPoll = 0.0;
};
