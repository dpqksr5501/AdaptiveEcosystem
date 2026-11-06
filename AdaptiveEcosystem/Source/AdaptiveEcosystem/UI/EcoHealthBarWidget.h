#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "EcoHealthBarWidget.generated.h"

/** Asset-free, passive display shared by creature representations and other health adapters. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoHealthBarWidget : public UUserWidget
{
	GENERATED_BODY()
public:
	void SetHealthFraction(float Fraction);
protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void ReleaseSlateResources(bool bReleaseChildren) override;
private:
	float HealthFraction = 0.f;
	TSharedPtr<class SProgressBar> Progress;
	TSharedPtr<class STextBlock> Label;
	void RefreshDisplay();
};
