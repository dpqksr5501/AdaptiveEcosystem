#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Core/EcoFoodPatchLayout.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "World/EcoVegetationField.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Serialization/BitWriter.h"
#include "Serialization/BitReader.h"
#include "HAL/IConsoleManager.h"
#include <limits>

namespace
{
    FEcoFoodPatchLayout Descriptor()
    {
        FEcoFoodPatchLayout D;
        D.RegionId = TEXT("PatchFixture"); D.Seed = 23; D.Epoch = 1;
        D.GridWidth = 30; D.PatchCount = 9; D.CellWidthCm = 400; D.OriginCm = FVector(1000,2000,3000);
        D.SettingsHash = D.CalculateHash(); return D;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFoodPatchLayoutGolden, "AdaptiveEcosystem.Vegetation.Patches.LayoutGolden",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFoodPatchLayoutGolden::RunTest(const FString&)
{
    // Literal golden values derived from installed UE5.8 RandomStream.h and TypeHash.h, not the helper under test.
    const float Golden[3][3] = {{-39.94348907470703f,135.54678344726562f,188.20420837402344f},
        {-112.51202392578125f,137.2528533935547f,229.8393096923828f},
        {129.78456115722656f,-119.2247314453125f,255.94424438476562f}};
    TArray<FEcoFoodPatchSample> Samples;
    TestTrue(TEXT("Bounded pure layout succeeds"), EcoFoodPatchLayout::GenerateCell(123,7,400,3,Samples));
    for (int32 I=0; I<3; ++I)
    {
        TestEqual(TEXT("Golden X draw"), Samples[I].OffsetX, Golden[I][0]);
        TestEqual(TEXT("Golden Y draw"), Samples[I].OffsetY, Golden[I][1]);
        TestEqual(TEXT("Golden yaw draw"), Samples[I].Yaw, Golden[I][2]);
    }
    const auto D = Descriptor();
    // Independent old render algorithm, every candidate and several cells/seed values, including maximum count.
    for (uint32 Seed : {0u, D.RegionSeed(), MAX_uint32}) for (int32 Cell : {0,7,899})
    {
        EcoFoodPatchLayout::GenerateCell(Seed,Cell,400,25,Samples);
        FRandomStream Legacy(int32(HashCombineFast(Seed,uint32(Cell))));
        for (int32 I=0;I<25;++I)
        {
            const float X=Legacy.FRandRange(-.42f,.42f)*400;
            const float Y=Legacy.FRandRange(-.42f,.42f)*400;
            const float Yaw=Legacy.FRandRange(0.f,360.f);
            if (Samples[I].OffsetX!=X || Samples[I].OffsetY!=Y || Samples[I].Yaw!=Yaw)
            { AddError(TEXT("Layout V1 changed the old draw order")); return false; }
        }
    }
    const auto Before = Samples;
    TestFalse(TEXT("Invalid counts are rejected"), EcoFoodPatchLayout::GenerateCell(0,0,400,26,Samples));
    TestFalse(TEXT("NaN cell size is rejected"), EcoFoodPatchLayout::GenerateCell(0,0,std::numeric_limits<float>::quiet_NaN(),9,Samples));
    TestEqual(TEXT("Invalid calls leave previous snapshot intact"), Samples.Num(), Before.Num());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFoodPatchIdentity, "AdaptiveEcosystem.Vegetation.Patches.IdentityAndGround",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFoodPatchIdentity::RunTest(const FString&)
{
    auto D=Descriptor(); FEcoFoodPatchCache Server, Client;
    if (!TestTrue(TEXT("Server initializes a bounded continuous cache"), Server.Initialize(D))) return false;
    TestTrue(TEXT("Client reconstructs identical descriptor"), Client.Initialize(D));
    TestEqual(TEXT("30x30x9 fixed patches"),Server.Patches.Num(),8100);
    for (int32 I=0;I<Server.Patches.Num();++I)
    {
        if (Server.Patches[I].RelativePosition!=Client.Patches[I].RelativePosition || Server.Patches[I].Yaw!=Client.Patches[I].Yaw)
        { AddError(TEXT("Server/client layout mismatch")); return false; }
        const auto& P=Server.Patches[I]; const int32 Cell=I/D.PatchCount;
        if (P.RelativePosition.X<(Cell%D.GridWidth)*400 || P.RelativePosition.X>(Cell%D.GridWidth+1)*400
            || P.RelativePosition.Y<(Cell/D.GridWidth)*400 || P.RelativePosition.Y>(Cell/D.GridWidth+1)*400 || P.bGroundUsable)
        { AddError(TEXT("Initial patches must stay in their cell and await ground")); return false; }
    }
    const FEcoFoodPatchId Id{D.RegionId,D.Epoch,7,2};
    const FVector Position=D.OriginCm+FVector(Server.Patches[7*9+2].RelativePosition)+FVector(0,0,123);
    TestTrue(TEXT("Authority ground correction applies"),Server.SetGround(Id,Position,FVector::UpVector,true));
    const auto* Storage=Server.Patches.GetData();
    TestTrue(TEXT("Same descriptor is a cache hit"),Server.Initialize(D));
    TestTrue(TEXT("Cache hit preserves allocation and ground"),Storage==Server.Patches.GetData()&&Server.Patches[65].bGroundUsable);
    TestFalse(TEXT("Ground cannot move patch XY"),Server.SetGround(Id,Position+FVector(1,0,0),FVector::UpVector,true));
    TestFalse(TEXT("Steep ground cannot become usable"),Server.SetGround(Id,Position,FVector::ForwardVector,true));
    Server.InvalidateGround();
    TestFalse(TEXT("Terrain revision immediately makes a target unavailable"),Server.Patches[65].bGroundUsable);
    auto Bad=D;Bad.PatchCount=25;Bad.SettingsHash=Bad.CalculateHash();
    TestFalse(TEXT("Changed layout cannot reuse an epoch"),Server.Initialize(Bad));
    Bad.Epoch=2;TestTrue(TEXT("Explicit next epoch replaces layout"),Server.Initialize(Bad));
    TestFalse(TEXT("Old target identity is rejected"),Id.IsValidFor(Server.Layout));
    TestFalse(TEXT("Old ground correction is rejected"),Server.SetGround(Id,Position,FVector::UpVector,true));
    auto Corrupt=Bad;Corrupt.SettingsHash^=1;
    TestFalse(TEXT("Unknown descriptor hash is rejected atomically"),Server.Initialize(Corrupt));
    TestEqual(TEXT("Previous good layout remains after failure"),Server.Layout.Epoch,2u);
    AddInfo(FString::Printf(TEXT("Patch record=%llu bytes; 22500 max-count patches allocated=%llu bytes"),
        uint64(sizeof(FEcoFoodPatchStatic)),uint64(Server.Patches.GetAllocatedSize())));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFoodPatchGroundBudget, "AdaptiveEcosystem.Vegetation.Patches.WorldGroundBudget",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFoodPatchGroundBudget::RunTest(const FString&)
{
    FEcoFoodPatchTraceBudget Budget;
    for (int32 Region=0;Region<4;++Region)
    { TestEqual(TEXT("Cell ground slice"),Budget.Take(100,12),12);TestEqual(TEXT("Patch ground slice"),Budget.Take(100,12),12); }
    TestEqual(TEXT("World budget cannot be spent again"),Budget.Take(100,96),0);
    TestEqual(TEXT("New frame resets ceiling"),Budget.Take(101,1000),96);
    TestEqual(TEXT("Negative request spends nothing"),Budget.Take(101,-1),0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFoodPatchAuthorityAnchors, "AdaptiveEcosystem.Vegetation.Patches.AuthorityAnchors",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFoodPatchAuthorityAnchors::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* Field=W.World->SpawnActor<AEcoVegetationField>();
    auto* Mesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!Field||!Mesh) return false;
    Field->RegionId=TEXT("PatchFixture");Field->ConfigureGrid(400,400,23);Field->Plants->SetStaticMesh(Mesh);
    auto D=Descriptor();D.GridWidth=1;D.OriginCm=FVector::ZeroVector;D.SettingsHash=D.CalculateHash();
    Field->PatchLayout=D;Field->PatchLayoutMode=1;
    auto& V=Field->VisualGrid.Cells.AddDefaulted_GetRef();
    V.Position=FVector_NetQuantize10(FVector(200,200,0));V.Food=V.Capacity=65535;
    Field->RefreshPlants(FVector(200,200,500),0);
    TestEqual(TEXT("No ground snapshot means no client trace fallback"),Field->Plants->GetInstanceCount(),0);
    FEcoFoodPatchCache Cache;Cache.Initialize(D);
    auto& Cell=Field->PatchGround.Cells.AddDefaulted_GetRef();
    Cell.Epoch=D.Epoch;Cell.SettingsHash=D.SettingsHash;Cell.Revision=1;Cell.ValidMask=(1u<<9)-1;
    for (const auto& P:Cache.Patches)
    {
        Cell.RelativePositions.Add(FVector_NetQuantize10(FVector(P.RelativePosition)+FVector(0,0,123)));
        Cell.Normals.Add(FVector_NetQuantizeNormal(FVector::UpVector));
    }
    // Exercise the actual wire codec: XY is reconstructed and the client has no local ground collider.
    FBitWriter Writer(65536,true); bool Success=false;
    Cell.NetSerialize(Writer,nullptr,Success);
    if (!TestTrue(TEXT("Complete cell wire write"),Success)) return false;
    FBitReader Reader(Writer.GetData(),Writer.GetNumBits()); FEcoFoodPatchGroundCell Received;
    Received.NetSerialize(Reader,nullptr,Success);
    if (!TestTrue(TEXT("Complete cell wire read"),Success)) return false;
    Cell=MoveTemp(Received);
    Field->RefreshPlants(FVector(200,200,500),1);
    TestEqual(TEXT("Authority ground renders even with no local collision floor"),Field->Plants->GetInstanceCount(),9);
    for (const auto& Entry:Field->RenderedPlants)
        TestEqual(TEXT("Independent client projection cannot relocate ground"),Entry.Value.GroundPosition.Z,123.);
    Field->CandidatesPerCell=1;Field->RefreshPlants(FVector(200,200,500),2);
    TestEqual(TEXT("Render settings cannot alter gameplay patch count"),Field->Plants->GetInstanceCount(),9);
    Cell.ValidMask&=~(1u<<3);++Cell.Revision;Field->RefreshPlants(FVector(200,200,500),3);
    TestEqual(TEXT("Invalid ground hides exactly that candidate"),Field->Plants->GetInstanceCount(),8);
    ++Field->PatchLayout.Epoch;Field->RefreshPlants(FVector(200,200,500),4);
    TestEqual(TEXT("Stale epoch cannot create ghost anchors"),Field->Plants->GetInstanceCount(),0);
    Cell.Epoch=Field->PatchLayout.Epoch;Cell.RelativePositions.Pop();
    TestFalse(TEXT("Partial cell snapshot rejected"),Cell.Matches(Field->PatchLayout));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFoodPatchWireSnapshot, "AdaptiveEcosystem.Vegetation.Patches.WireSnapshot",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFoodPatchWireSnapshot::RunTest(const FString&)
{
    for (int32 Count:{1,9,25})
    {
        auto D=Descriptor();D.PatchCount=Count;D.SettingsHash=D.CalculateHash();
        FEcoFoodPatchGroundCell Source;
        Source.Cell=899;Source.Epoch=D.Epoch;Source.SettingsHash=D.SettingsHash;Source.Revision=7;Source.ValidMask=(1u<<Count)-1;
        for (int32 I=0;I<Count;++I)
        { Source.RelativePositions.Add(FVector_NetQuantize10(FVector(100+I,200+I,-123.49+I*17.17)));Source.Normals.Add(FVector_NetQuantizeNormal(FVector::UpVector)); }
        FBitWriter Writer(65536,true);bool Success=false;Source.NetSerialize(Writer,nullptr,Success);
        TestTrue(TEXT("Bounded cell encodes"),Success);
        // Height-only payload prevents the 170KB initial actor bunch seen with raw FVector arrays.
        TestTrue(TEXT("Height codec has a bounded bit cost"),Writer.GetNumBits()<=160+21*Count);
        FBitReader Reader(Writer.GetData(),Writer.GetNumBits());FEcoFoodPatchGroundCell Received;
        Received.NetSerialize(Reader,nullptr,Success);
        TestTrue(TEXT("Descriptor identity survives actual bit serialization"),Success&&Received.Matches(D)&&Received.Cell==899&&Received.Revision==7);
        TestEqual(TEXT("Slot validity mask survives"),Received.ValidMask,Source.ValidMask);
        for (int32 I=0;I<Count;++I)
            TestTrue(TEXT("Wire anchor height stays within half a centimeter"),FMath::Abs(Received.RelativePositions[I].Z-Source.RelativePositions[I].Z)<=.50001);
        FBitReader Truncated(Writer.GetData(),Writer.GetNumBits()-1);FEcoFoodPatchGroundCell Partial;
        auto* EnsureOverflow=IConsoleManager::Get().FindConsoleVariable(TEXT("net.BitReader.EnsureOnOverflow"));
        const int32 PreviousEnsure=EnsureOverflow->GetInt();
        EnsureOverflow->Set(0,ECVF_SetByCode);
        AddExpectedErrorPlain(TEXT("FBitReader::SetOverflowed() called!"), EAutomationExpectedErrorFlags::Contains, 1);
        Partial.NetSerialize(Truncated,nullptr,Success);
        EnsureOverflow->Set(PreviousEnsure,ECVF_SetByCode);
        TestFalse(TEXT("Truncated ground snapshots are rejected"),Success);
    }
    return true;
}
#endif
