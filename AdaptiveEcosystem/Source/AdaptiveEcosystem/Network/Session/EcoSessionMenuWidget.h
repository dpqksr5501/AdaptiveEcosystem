#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "EcoSessionMenuWidget.generated.h"

class UButton;
class UCheckBox;
class UComboBoxString;
class UEditableTextBox;
class UTextBlock;
class UEcoSessionSubsystem;

/** Native room browser, usable without creating or modifying a Widget Blueprint. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSessionMenuWidget : public UUserWidget
{
    GENERATED_BODY()
public:
    UFUNCTION() void Refresh();
protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual void NativeConstruct() override;
    virtual void NativeDestruct() override;
    virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
private:
    void BuildMenu();
    UEcoSessionSubsystem* Session() const;
    UButton* MakeButton(const FString& Label);
    UFUNCTION() void Host();
    UFUNCTION() void Find();
    UFUNCTION() void Join();
    UFUNCTION() void Leave();
    UFUNCTION() void Close();
    UPROPERTY(Transient) TObjectPtr<UTextBlock> StatusText;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> PlayersText;
    UPROPERTY(Transient) TObjectPtr<UEditableTextBox> RoomName;
    UPROPERTY(Transient) TObjectPtr<UCheckBox> LAN;
    UPROPERTY(Transient) TObjectPtr<UComboBoxString> Rooms;
    UPROPERTY(Transient) TObjectPtr<UButton> HostButton;
    UPROPERTY(Transient) TObjectPtr<UButton> FindButton;
    UPROPERTY(Transient) TObjectPtr<UButton> JoinButton;
    UPROPERTY(Transient) TObjectPtr<UButton> LeaveButton;
    int32 DisplayRevision = -1;
    int32 DisplayCount = -1;
};

