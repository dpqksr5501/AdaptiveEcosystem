#include "Network/Session/EcoSessionMenuWidget.h"
#include "Network/Session/EcoSessionSubsystem.h"
#include "Network/Session/EcoSessionSettings.h"
#include "Network/EcoGameState.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/CheckBox.h"
#include "Components/ComboBoxString.h"
#include "Components/EditableTextBox.h"
#include "Components/HorizontalBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "InputCoreTypes.h"

UEcoSessionSubsystem* UEcoSessionMenuWidget::Session() const
{
    return GetGameInstance()?GetGameInstance()->GetSubsystem<UEcoSessionSubsystem>():nullptr;
}

UButton* UEcoSessionMenuWidget::MakeButton(const FString& Label)
{
    auto* Button=WidgetTree->ConstructWidget<UButton>();
    auto* Text=WidgetTree->ConstructWidget<UTextBlock>();
    Text->SetText(FText::FromString(Label));
    auto Font=Text->GetFont(); Font.Size=20; Text->SetFont(Font);
    Text->SetColorAndOpacity(FSlateColor(FLinearColor(.04f,.07f,.1f)));
    Button->AddChild(Text);
    return Button;
}

void UEcoSessionMenuWidget::BuildMenu()
{
    SetIsFocusable(true);
    auto* Canvas=WidgetTree->ConstructWidget<UCanvasPanel>();
    WidgetTree->RootWidget=Canvas;
    auto* Border=WidgetTree->ConstructWidget<UBorder>();
    Border->SetBrushColor(FLinearColor(.025f,.045f,.065f,.97f));
    Border->SetPadding(FMargin(28));
    auto* CanvasSlot=Canvas->AddChildToCanvas(Border);
    CanvasSlot->SetAnchors(FAnchors(.5f,.5f));
    CanvasSlot->SetAlignment(FVector2D(.5f,.5f));
    CanvasSlot->SetSize(FVector2D(820,530));
    auto* Box=WidgetTree->ConstructWidget<UVerticalBox>();
    Border->SetContent(Box);
    auto Add=[Box](UWidget* Widget,float BottomSpace=10.f)
    { auto* Slot=Box->AddChildToVerticalBox(Widget); Slot->SetPadding(FMargin(0,0,0,BottomSpace)); };

    auto* Title=WidgetTree->ConstructWidget<UTextBlock>();
    Title->SetText(FText::FromString(TEXT("Adaptive Ecosystem · 멀티플레이")));
    auto Font=Title->GetFont(); Font.Size=25; Title->SetFont(Font); Add(Title,18);
    PlayersText=WidgetTree->ConstructWidget<UTextBlock>();
    auto BodyFont=PlayersText->GetFont(); BodyFont.Size=20; PlayersText->SetFont(BodyFont);
    Add(PlayersText);
    RoomName=WidgetTree->ConstructWidget<UEditableTextBox>();
    RoomName->SetHintText(FText::FromString(TEXT("만들 방의 이름")));
    RoomName->SetForegroundColor(FLinearColor(.04f,.07f,.1f));
    RoomName->SetText(FText::FromString(TEXT("JWJ 생태계"))); Add(RoomName);
    LAN=WidgetTree->ConstructWidget<UCheckBox>();
    auto* LANText=WidgetTree->ConstructWidget<UTextBlock>();
    LANText->SetFont(BodyFont);
    LANText->SetText(FText::FromString(TEXT("  로컬망 시험 (Steam 없이)")));
    LAN->SetContent(LANText); Add(LAN);
    auto* Actions=WidgetTree->ConstructWidget<UHorizontalBox>();
    HostButton=MakeButton(TEXT("  방 만들기  "));
    FindButton=MakeButton(TEXT("  방 검색  "));
    Actions->AddChild(HostButton); Actions->AddChild(FindButton); Add(Actions,16);
    Rooms=WidgetTree->ConstructWidget<UComboBoxString>();
    Rooms->SetMaxListHeight(210); Add(Rooms);
    auto* JoinActions=WidgetTree->ConstructWidget<UHorizontalBox>();
    JoinButton=MakeButton(TEXT("  선택한 방 참가  "));
    LeaveButton=MakeButton(TEXT("  방 나가기  "));
    auto* CloseButton=MakeButton(TEXT("  닫기 (F10 / Esc)  "));
    JoinActions->AddChild(JoinButton); JoinActions->AddChild(LeaveButton); JoinActions->AddChild(CloseButton); Add(JoinActions,18);
    StatusText=WidgetTree->ConstructWidget<UTextBlock>();
    StatusText->SetFont(BodyFont); StatusText->SetWrapTextAt(764); Add(StatusText);
    HostButton->OnClicked.AddDynamic(this,&ThisClass::Host);
    FindButton->OnClicked.AddDynamic(this,&ThisClass::Find);
    JoinButton->OnClicked.AddDynamic(this,&ThisClass::Join);
    LeaveButton->OnClicked.AddDynamic(this,&ThisClass::Leave);
    CloseButton->OnClicked.AddDynamic(this,&ThisClass::Close);
}

TSharedRef<SWidget> UEcoSessionMenuWidget::RebuildWidget()
{
    if (!WidgetTree) WidgetTree=NewObject<UWidgetTree>(this);
    if (!WidgetTree->RootWidget) BuildMenu();
    return Super::RebuildWidget();
}

void UEcoSessionMenuWidget::NativeConstruct()
{
    Super::NativeConstruct();
    if (auto* S=Session())
    {
        S->OnUpdated.RemoveDynamic(this,&ThisClass::Refresh);
        S->OnUpdated.AddDynamic(this,&ThisClass::Refresh);
    }
    Refresh();
}

void UEcoSessionMenuWidget::NativeDestruct()
{
    if (auto* S=Session()) S->OnUpdated.RemoveDynamic(this,&ThisClass::Refresh);
    Super::NativeDestruct();
}

void UEcoSessionMenuWidget::Refresh()
{
    auto* S=Session();
    if (!S || !StatusText) return;
    StatusText->SetText(FText::FromString(S->Status));
    const auto* GS=GetWorld()?GetWorld()->GetGameState<AEcoGameState>():nullptr;
    const auto* Settings=GetDefault<UEcoSessionSettings>();
    PlayersText->SetText(FText::FromString(FString::Printf(TEXT("접속 %d / %d명 · Host 1 + Client 최대 %d\n%s"),
        GS?GS->GetConnectedPlayerCount():0, GS?GS->GetMaxPlayers():Settings->TotalPlayers(false), Settings->TotalPlayers(true),
        GS && GS->IsMassReplicationReady()?TEXT("생태계 준비 완료"):TEXT("생태계 준비 중"))));
    const bool bLocal=GetWorld() && GetWorld()->GetNetMode()==NM_Standalone;
    HostButton->SetIsEnabled(bLocal && !S->IsBusy() && S->State!=EEcoSessionState::InSession);
    FindButton->SetIsEnabled(bLocal && !S->IsBusy() && S->State!=EEcoSessionState::InSession);
    JoinButton->SetIsEnabled(bLocal && !S->IsBusy() && !S->Results.IsEmpty());
    LeaveButton->SetIsEnabled(!S->IsBusy());
    LAN->SetIsEnabled(bLocal && !S->IsBusy());
    if (DisplayRevision!=S->SearchRevision || DisplayCount!=S->Results.Num())
    {
        DisplayRevision=S->SearchRevision; DisplayCount=S->Results.Num();
        Rooms->ClearOptions();
        if (S->Results.IsEmpty()) Rooms->AddOption(TEXT("방 검색을 눌러 참가할 방을 찾아보세요."));
        int32 Row=0;
        for (const auto& Entry:S->Results)
            Rooms->AddOption(FString::Printf(TEXT("%d. %s  ·  %s  ·  %d/%d명%s"),++Row,*Entry.Name,*Entry.Host,Entry.Players,Entry.Capacity,
                Entry.bCompatible?TEXT(""):TEXT("  [버전 다름]")));
        Rooms->SetSelectedIndex(0);
    }
}

void UEcoSessionMenuWidget::Host() { if(auto* S=Session()) S->HostSession(RoomName->GetText().ToString(),LAN->IsChecked()); }
void UEcoSessionMenuWidget::Find() { if(auto* S=Session()) S->FindSessions(LAN->IsChecked()); }
void UEcoSessionMenuWidget::Join() { if(auto* S=Session()) S->JoinSession(Rooms->GetSelectedIndex(),DisplayRevision); }
void UEcoSessionMenuWidget::Leave() { if(auto* S=Session()) S->LeaveSession(); }
void UEcoSessionMenuWidget::Close() { if(auto* S=Session()) S->CloseSessionMenu(); }

FReply UEcoSessionMenuWidget::NativeOnKeyDown(const FGeometry& Geometry,const FKeyEvent& Event)
{
    if (Event.GetKey()==EKeys::Escape || Event.GetKey()==EKeys::F10) { Close(); return FReply::Handled(); }
    return Super::NativeOnKeyDown(Geometry,Event);
}

