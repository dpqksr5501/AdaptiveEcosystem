#include "UI/EcoHealthBarWidget.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Notifications/SProgressBar.h"
#include "Widgets/Text/STextBlock.h"
#include "Styling/CoreStyle.h"
#include "Brushes/SlateColorBrush.h"

TSharedRef<SWidget> UEcoHealthBarWidget::RebuildWidget()
{
	static const FSlateColorBrush EmptyHealthBrush(FLinearColor(.045f, .045f, .045f));
	TSharedRef<SWidget> Result = SNew(SBorder)
		.BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
		.BorderBackgroundColor(FLinearColor(.015f, .015f, .015f, .95f))
		.Padding(2.f)
		[
			SNew(SOverlay)
			+ SOverlay::Slot()
			[
				SAssignNew(Progress, SProgressBar)
				.BackgroundImage(&EmptyHealthBrush)
				.FillImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
				.BorderPadding(FVector2D::ZeroVector)
				.FillColorAndOpacity(FLinearColor(.1f, .8f, .2f))
			]
			+ SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Center)
			[
				SAssignNew(Label, STextBlock)
				.Font(FCoreStyle::GetDefaultFontStyle("Bold", 9))
				.ColorAndOpacity(FLinearColor::White)
				.ShadowOffset(FVector2D(1, 1)).ShadowColorAndOpacity(FLinearColor::Black)
			]
		];
	RefreshDisplay();
	return Result;
}

void UEcoHealthBarWidget::SetHealthFraction(float Fraction)
{
	const float NewFraction = FMath::IsFinite(Fraction) ? FMath::Clamp(Fraction, 0.f, 1.f) : 0.f;
	if (NewFraction == HealthFraction) return;
	HealthFraction = NewFraction;
	RefreshDisplay();
}

void UEcoHealthBarWidget::RefreshDisplay()
{
	if (Progress)
	{
		Progress->SetPercent(HealthFraction);
		Progress->SetFillColorAndOpacity(HealthFraction > .5f ? FLinearColor(.08f, .65f, .18f)
			: HealthFraction > .25f ? FLinearColor(.9f, .5f, .02f) : FLinearColor(.8f, .04f, .03f));
	}
	if (Label) Label->SetText(FText::FromString(FString::Printf(TEXT("%d%%"), FMath::RoundToInt(HealthFraction * 100.f))));
}

void UEcoHealthBarWidget::ReleaseSlateResources(bool bReleaseChildren)
{
	Super::ReleaseSlateResources(bReleaseChildren);
	Progress.Reset();
	Label.Reset();
}
