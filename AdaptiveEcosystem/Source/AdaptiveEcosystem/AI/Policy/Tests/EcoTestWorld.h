// 자동화 테스트가 같이 쓰는 월드·프로세서 헬퍼.
//
// 파이프라인 테스트와 포식 테스트가 둘 다 "코드로 월드를 만들고 프로세서를 직접 돌린다".
// 각 파일에 따로 두면 유니티 빌드에서 같은 이름이 두 번 정의될 수 있어 여기로 뺐다.

#pragma once

#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "MassEntityManager.h"
#include "MassExecutionContext.h"
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

	/** 프로세서 하나를 한 틱 돌린다. */
	inline void RunProcessor(UMassProcessor& Processor, FMassEntityManager& EM, float Dt)
	{
		FMassExecutionContext Context(EM, Dt);
		// 프로세서가 소유한 쿼리(FMassEntityQuery(*this))는 Processor 타입 컨텍스트를
		// 요구한다. 기본값 Local 로 두면 MassEntityQuery.cpp 의 어설션에 걸린다.
		Context.SetExecutionType(EMassExecutionContextType::Processor);
		Processor.CallExecute(EM, Context);
	}
}

#endif // WITH_DEV_AUTOMATION_TESTS
