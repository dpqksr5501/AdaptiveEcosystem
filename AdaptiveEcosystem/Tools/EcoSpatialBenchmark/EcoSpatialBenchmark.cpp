// Reproducible cumulative ablation: full -> kin -> threat -> wolf.
// CSV stdout, diagnostics stderr. No Unreal world or rendering is measured.
#include "EcoWorldV3.h"
#include <cstdio>
#include <cstring>
#include <stdexcept>

namespace W = EcoWorldV3;
namespace O = EcoObservationV3;

static void Require(bool Ok, const char* What)
{
    if (!Ok) throw std::runtime_error(What);
}

static void Mode(W::FReferenceWorld& R, int Stage)
{
    R.World.bSpatialKin = Stage >= 1;
    R.World.bSpatialThreat = Stage >= 2;
    R.World.bSpatialWolf = Stage >= 3;
    W::ObserveAndDecideAll(R.World,R.Views.data(),R.NumHerbivores(),R.ThreatPtrs.data(),R.NumThreats());
}

static void Same(const W::FReferenceWorld& A, const W::FReferenceWorld& B)
{
    Require(A.World.Rng.State==B.World.Rng.State && A.World.T==B.World.T && A.World.Food.Food==B.World.Food.Food
        && A.World.PredEma==B.World.PredEma,"world/food/rng");
    Require(A.World.Stats.Caught==B.World.Stats.Caught && A.World.Stats.Starved==B.World.Stats.Starved
        && A.World.Stats.FoodEaten==B.World.Stats.FoodEaten,"outcomes");
    for (int I=0; I<A.NumHerbivores(); ++I)
    {
        const auto& X=A.Bodies[I]; const auto& Y=B.Bodies[I];
        Require(X.Pos.X==Y.Pos.X && X.Pos.Y==Y.Pos.Y && X.Head.X==Y.Head.X && X.Head.Y==Y.Head.Y
            && X.Energy==Y.Energy && X.Reserve==Y.Reserve && X.DeathCause==Y.DeathCause && X.Generation==Y.Generation,"body");
        const auto& P=A.Perceptions[I]; const auto& Q=B.Perceptions[I];
        Require(std::memcmp(P.Obs,Q.Obs,sizeof(P.Obs))==0,"observation bits");
        Require(P.Kin.ToCentroid.X==Q.Kin.ToCentroid.X && P.Kin.ToCentroid.Y==Q.Kin.ToCentroid.Y
            && P.Kin.Separation.X==Q.Kin.Separation.X && P.Kin.Separation.Y==Q.Kin.Separation.Y
            && P.Threat.Nearest==Q.Threat.Nearest && P.Threat.NearestEv==Q.Threat.NearestEv,"geometry");
        const auto& D=A.Decisions[I]; const auto& E=B.Decisions[I];
        Require(D.Request==E.Request && D.ExecutedBehavior==E.ExecutedBehavior && D.KeepMode==E.KeepMode
            && std::memcmp(D.Logits,E.Logits,sizeof(D.Logits))==0 && std::memcmp(D.Mask,E.Mask,sizeof(D.Mask))==0,"decision");
        const auto& S=A.Reps[I]; const auto& T=B.Reps[I];
        Require(S.Behavior==T.Behavior && S.Phase==T.Phase && S.Seq==T.Seq && S.StepsIn==T.StepsIn
            && S.LockLeft==T.LockLeft && S.EvWait==T.EvWait && S.HideTarget==T.HideTarget && S.Recency==T.Recency,"arbiter");
    }
    for (int I=0; I<A.NumThreats(); ++I)
    {
        const auto& X=A.Threats[I]; const auto& Y=B.Threats[I];
        Require(X.State.PosX==Y.State.PosX && X.State.PosY==Y.State.PosY && X.State.Target==Y.State.Target
            && X.State.Cooldown==Y.State.Cooldown && X.State.StalkState==Y.State.StalkState
            && X.Last.Caught==Y.Last.Caught && X.Last.Target==Y.Last.Target,"wolf");
    }
}

static void Boundaries()
{
    EcoSpatialV3::FGrid Grid;
    std::vector<O::FKinInput> Kin={{-20,0,0},{0,0,0},{20,0,1},{20.0000001,0,0},{0,5,0},{0,-5,0}};
    Kin.resize(80, {10000,10000,0});
    Grid.Build(static_cast<int>(Kin.size()),20,[&](int I){return W::FVec2{Kin[I].X,Kin[I].Y};});
    std::vector<int> Candidates;
    const auto Rows=Grid.Query(0,0,20,Candidates);
    const auto A=O::PerceiveKin(1,{0,0},{1,0},Kin.data(),static_cast<int>(Kin.size()));
    const auto B=O::PerceiveKin(1,{0,0},{1,0},Kin.data(),static_cast<int>(Kin.size()),O::kR1bObsConfig,Rows);
    Require(A.KinCount==B.KinCount && A.Separation.X==B.Separation.X && A.Separation.Y==B.Separation.Y,"negative/boundary/duplicate");
    // Hearing outside vision, sleeping threat, equal-distance target, external row.
    std::vector<O::FThreatInput> Threats(80);
    for (auto& T : Threats) T.X=10000;
    Threats[0].X=-35; Threats[0].HearR=40;
    Threats[1].X=35; Threats[1].HearR=40;
    Threats[2].X=1; Threats[2].bAsleep=true;
    Threats[3].X=50;
    Grid.Build(80,20,[&](int I){return W::FVec2{Threats[I].X,Threats[I].Y};});
    const auto TRows=Grid.Query(0,0,40,Candidates);
    const auto T0=O::PerceiveThreats({0,0},{1,0},20,1,1,Threats.data(),80);
    const auto T1=O::PerceiveThreats({0,0},{1,0},20,1,1,Threats.data(),80,O::kR1bObsConfig,TRows);
    Require(T0.PredCount==T1.PredCount && T0.Nearest==T1.Nearest && T1.Nearest==0,"hearing/tie");
    Require(Grid.Query(0,0,1.e100,Candidates).Indices==nullptr,"large query fallback");
}

int main()
{
    try
    {
        Boundaries();
        // Dense, sparse, respawn, night, ranged, pack, shelter, and uncapped hearing.
        for (int Scenario=0; Scenario<4; ++Scenario)
        {
            W::FWorldConfig C; C.NumHerbivores=128; C.Seed=20000+Scenario;
            C.WorldSize=Scenario==0?60:200; C.bPlayerProxy=true;
            C.RealismHearing.bEnabled=true;
            C.NumStalkers=32; C.NumChasers=32;
            C.PackHunt.bEnabled=Scenario>=2;
            C.bShelterSafe=Scenario==3;
            C.Covers=W::QuadCovers(C.WorldSize,7);
            W::FReferenceWorld A,B; A.Init(C); B.Init(C); Mode(A,0); Mode(B,3); Same(A,B);
            for (int T=0; T<900; ++T) { A.StepOnce(); B.StepOnce(); Same(A,B); }
        }
        std::fprintf(stderr,"PASS: boundary cases + 4 x 900 full-world steps, exact observations and outcomes\n");
        std::puts("layout,deer,wolves,trial,stage,steps,wall_ms,build_ms,kin_ms,threat_ms,wolf_ms,kin_full,kin_candidates,threat_full,threat_candidates,wolf_full,wolf_candidates");
        for (int Dense=0; Dense<2; ++Dense)
        for (int N : {128,1024})
        for (int Trial=0; Trial<3; ++Trial)
        for (int Stage=0; Stage<4; ++Stage)
        {
            W::FWorldConfig C; C.NumHerbivores=N; C.WorldSize=Dense?60:200;
            C.NumStalkers=N/32; C.NumChasers=N/32; C.NumRanged=1; C.NumNocturnal=1;
            C.Seed=12345; C.RealismHearing.bEnabled=true;
            W::FReferenceWorld R; R.Init(C); Mode(R,Stage);
            for (int T=0; T<10; ++T) R.StepOnce();
            R.World.SearchDiagnostics.bEnabled=true; R.World.SearchDiagnostics.Reset();
            const auto Start=std::chrono::steady_clock::now();
            for (int T=0; T<100; ++T) R.StepOnce();
            const double Ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-Start).count();
            const auto& D=R.World.SearchDiagnostics;
            std::printf("%s,%d,%d,%d,%d,100,%.6f,%.6f,%.6f,%.6f,%.6f,%llu,%llu,%llu,%llu,%llu,%llu\n",
                Dense?"dense":"spread",N,R.NumThreats(),Trial,Stage,Ms,D.Build.Milliseconds,D.Kin.Milliseconds,D.Threat.Milliseconds,D.Wolf.Milliseconds,
                static_cast<unsigned long long>(D.Kin.FullCandidates),static_cast<unsigned long long>(D.Kin.Candidates),
                static_cast<unsigned long long>(D.Threat.FullCandidates),static_cast<unsigned long long>(D.Threat.Candidates),
                static_cast<unsigned long long>(D.Wolf.FullCandidates),static_cast<unsigned long long>(D.Wolf.Candidates));
        }
        return 0;
    }
    catch (const std::exception& E) { std::fprintf(stderr,"FAIL: %s\n",E.what()); return 1; }
}
