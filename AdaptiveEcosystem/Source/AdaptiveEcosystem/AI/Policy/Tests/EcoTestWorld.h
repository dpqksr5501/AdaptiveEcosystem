// 자동화 테스트가 같이 쓰는 월드·프로세서 헬퍼.
//
// 파이프라인 테스트와 포식 테스트가 둘 다 "코드로 월드를 만들고 프로세서를 직접 돌린다".
// 각 파일에 따로 두면 유니티 빌드에서 같은 이름이 두 번 정의될 수 있어 여기로 뺐다.
// 여기 있는 함수는 전부 inline 이다 — 이 헤더는 여러 번역 단위에 들어간다.

#pragma once

#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorFragments.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntityView.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "MassProcessor.h"

namespace EcoTest
{
	/** 테스트용 월드. 서브시스템이 만들어지도록 엔진에 알린다. */
	struct FScopedTestWorld
	{
		UWorld* World = nullptr;

		FScopedTestWorld()
		{
			World = UWorld::CreateWorld(EWorldType::Game, /*bInformEngineOfWorld*/ true);
			if (World && GEngine)
			{
				FWorldContext& Ctx = GEngine->CreateNewWorldContext(EWorldType::Game);
				Ctx.SetCurrentWorld(World);
			}
		}

		~FScopedTestWorld()
		{
			if (World)
			{
				if (GEngine)
				{
					GEngine->DestroyWorldContext(World);
				}
				World->DestroyWorld(false);
			}
		}

		FScopedTestWorld(const FScopedTestWorld&) = delete;
		FScopedTestWorld& operator=(const FScopedTestWorld&) = delete;
	};

	/**
	 * 프로세서 하나를 한 틱 돌린다.
	 *
	 * 컨텍스트는 EntityManager 가 만든다 — 그래야 지연 명령 버퍼(Defer())가 묶인다. 생성자로 직접
	 * 만들면 버퍼가 없어 Defer() 가 null 을 역참조한다. 명령은 엔진처럼 페이즈 끝(FlushPhase)에서만
	 * 반영한다.
	 */
	inline void RunProcessor(UMassProcessor& Processor, FMassEntityManager& EM, float Dt)
	{
		FMassExecutionContext Context = EM.CreateExecutionContext(Dt);
		// 프로세서가 소유한 쿼리(FMassEntityQuery(*this))는 Processor 타입 컨텍스트를
		// 요구한다. 기본값 Local 로 두면 MassEntityQuery.cpp 의 어설션에 걸린다.
		Context.SetExecutionType(EMassExecutionContextType::Processor);
		Context.SetFlushDeferredCommands(false);
		Processor.CallExecute(EM, Context);
	}

	/** 처리 페이즈 끝의 명령 반영(OnPhaseEnd) 대역. 한 틱의 프로세서를 다 돌린 뒤 부른다. */
	inline void FlushPhase(FMassEntityManager& EM)
	{
		EM.FlushCommands();
	}

	/**
	 * 초식 아키타입 구성. 트레잇(UEcoHerbivoreTrait), 테스트 스포너(AEcoPolicyTestSpawner)와
	 * 같아야 한다 — 하나를 바꾸면 세 곳을 같이 바꾼다.
	 */
	inline TArray<const UScriptStruct*> HerbivoreComposition()
	{
		return {
			FTransformFragment::StaticStruct(),
			FMassVelocityFragment::StaticStruct(),
			FEcoSteeringGeometryFragment::StaticStruct(),
			FEcoObservationFragment::StaticStruct(),
			FEcoPolicyOutputFragment::StaticStruct(),
			FEcoPolicyRuntimeFragment::StaticStruct(),
			FEcoVitalsFragment::StaticStruct(),
			FEcoHerbivoreTag::StaticStruct(),
			FMassCustomMovementTag::StaticStruct(),
			FEcoAliveTag::StaticStruct(),
		};
	}

	template <typename TTag>
	inline bool HasTag(const FMassEntityManager& EM, FMassEntityHandle E)
	{
		return FMassEntityView(EM, E).HasTag<TTag>();
	}
}

#endif // WITH_DEV_AUTOMATION_TESTS
