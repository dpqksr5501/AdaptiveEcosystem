# 개발자 Debug 명령

`UEcoDebugCommandSubsystem`은 개발용 콘솔 명령의 공용 등록 지점이다. 기능별 Debug Subsystem이 자기 명령을 등록하고, 등록된 서버/Standalone World가 끝나면 공용 등록 지점이 명령을 해제한다. 여러 PIE World가 같은 명령 이름을 등록해도 실행 시 콘솔이 전달한 World의 핸들러만 호출한다. Client와 Shipping에서는 이 Subsystem이 생성되지 않는다.

새 기능은 별도 `UWorldSubsystem`에서 `InitializeDependency<UEcoDebugCommandSubsystem>()`를 선언하고, World 준비 시 다음처럼 등록한다. 핸들러는 특정 World나 Actor 포인터를 캡처하지 말고 전달받은 World에서 필요한 권위 Subsystem을 조회한다. 상태 변경은 해당 기능의 소유 계층에 요청한다.

```cpp
if (UEcoDebugCommandSubsystem* Commands = InWorld.GetSubsystem<UEcoDebugCommandSubsystem>())
{
    Commands->RegisterCommand(TEXT("Debug.MyFeature"), TEXT("Run MyFeature in this server world."),
        [](UWorld& World, const TArray<FString>& Args)
        {
            // Validate Args; call the authoritative feature subsystem for World.
        });
}
```

명령 이름은 전역 ConsoleManager에 등록되므로 기존 이름과 충돌할 수 없다. 등록과 실행은 Game Thread에서 처리한다. Debug 핸들러가 Mass Entity나 지역 식량을 직접 변경하지 않도록 한다.

## 기아 이벤트

`UEcoStarvationDebugSubsystem`이 실제로 배치된 `AEcologyRegion` 각각에 `Debug.Starvation.<RegionId>`를 자동 등록한다. 예를 들어 `RegionId=Forest_A`이면 PIE 게임 뷰포트 콘솔에서 다음을 실행한다.

```text
Debug.Starvation.Forest_A
```

추가로 `Debug.Starvation Forest_A`도 쓸 수 있다. 후자는 World 시작 뒤에 등록된 지역에도 사용 가능한 일반형이다. 지역 이름은 `AEcologyRegion.RegionId`와 정확히 일치해야 한다. 명령은 입력 시점의 서버 시간에 이벤트를 예약하며, **시뮬레이션이 그 시각에 도달하면 해당 지역 Food를 정확히 0으로 만든다**. 처리가 밀린 경우 이전 시각의 스폰/소비에 소급 적용하지 않는다. 이는 낮밤 자동 이벤트와 같은 자원 장부에 `EventLoss`로 기록된다. 같은 지역의 중복 예약과 잘못된 지역은 거부한다. Forest_A의 낮 자동 이벤트는 기본 비활성화이며, Project Settings에서 다시 켤 수 있다. Forest_B의 밤 이벤트와 개체의 정기 소비는 별도 설정이다.

Standalone 또는 Listen Server 게임 뷰포트에서 사용한다. Client 뷰포트에서 입력하면 권위 World가 없어 거부된다. Output Log의 `[Eco Debug] Starvation queued`, `[Eco Food Event] Source=Debug.Starvation`, `[Eco Food] ... After=0 ... Depleted=1` 순서로 확인한다. 식량 0 지역의 추가 스폰은 생략되지만, M3.2에서는 개체 이주가 아직 구현되지 않아 기존 개체 수와 Box 위치는 즉시 바뀌지 않는다.
