#pragma once

#include "Core/EcoActivityTypes.h"
#include "Creature/Runtime/EcoFaunaExperience.h"

namespace EcoFaunaSocial
{
	struct FProfile
	{
		double RangeCm;
		double Interval;
		double FamiliarityWeight;
	};

	inline const TMap<FName, FProfile>& Profiles()
	{
		static const TMap<FName, FProfile> Values{
			{TEXT("Herbivore"), {750., 15., .65}}, {TEXT("Wolf"), {650., 17., .90}},
			{TEXT("Buffalo"), {700., 17., .75}}, {TEXT("Horse"), {650., 15., .60}},
			{TEXT("Bighorn"), {540., 19., .72}}, {TEXT("Pig"), {480., 21., .62}},
			{TEXT("Jackrabbit"), {350., 23., .48}}, {TEXT("Rat"), {240., 16., .55}},
			{TEXT("Fox"), {400., 25., .72}}, {TEXT("Leopard"), {430., 34., .95}},
			{TEXT("Mink"), {320., 26., .80}}, {TEXT("Crow"), {620., 14., .61}},
			{TEXT("GoldenEagle"), {620., 35., .90}}, {TEXT("AriakeCatfish"), {350., 25., .65}},
			{TEXT("CommonCarp"), {450., 16., .58}}, {TEXT("UnidentifiedFish"), {300., 18., .50}},
		};
		return Values;
	}

	enum class EMedium : uint8 { Ground, Air, Water };
	enum class ESignal : uint8 { None, Offer, Reply };
	inline constexpr uint16 AlarmPulse = 1 << 13;

	inline uint16 Pack(ESignal Signal, double Yaw)
	{
		return uint16((uint16(Signal) << 14) | (uint16(FRotator::CompressAxisToShort(Yaw) >> 3)));
	}

	inline ESignal Signal(uint16 Packed) { return ESignal(Packed >> 14); }
	inline double Yaw(uint16 Packed) { return FRotator::DecompressAxisFromShort(uint16((Packed & (AlarmPulse - 1)) << 3)); }

	inline bool IsActivityCompatible(EEcoSpeciesActivity Activity)
	{
		switch (Activity)
		{
		case EEcoSpeciesActivity::Hold: case EEcoSpeciesActivity::Wander: case EEcoSpeciesActivity::Graze:
		case EEcoSpeciesActivity::Rest: case EEcoSpeciesActivity::SatedRest: case EEcoSpeciesActivity::Regroup:
		case EEcoSpeciesActivity::Fly: case EEcoSpeciesActivity::Swim: return true;
		default: return false;
		}
	}

	inline bool IsReady(const FProfile& Profile, const FEcoFaunaLongTermExperience* Memory, double Now)
	{
		return !Memory || Memory->LastSocialAt < 0.
			|| Now >= Memory->LastSocialAt + Profile.Interval / Memory->AssociationFactor(Now);
	}

	inline double Cost(const FProfile& Profile, double Distance, double Familiarity)
	{
		return Distance / (1. + Profile.FamiliarityWeight * Familiarity);
	}

	struct FExchange
	{
		int64 Peer = 0;
		double Started = 0.;
	};
}
