#pragma once
#include "UObject/Interface.h"
#include "EcoAttackWindowReceiver.generated.h"
UENUM()
enum class EEcoAttackWindow : uint8 { Input, Hit, Branch };
UINTERFACE(MinimalAPI, meta=(CannotImplementInterfaceInBlueprint))
class UEcoAttackWindowReceiver : public UInterface { GENERATED_BODY() };
class IEcoAttackWindowReceiver
{
    GENERATED_BODY()
public:
    virtual void ReceiveAttackWindow(EEcoAttackWindow Window, bool bOpen, class UAnimSequenceBase* Animation) = 0;
};
