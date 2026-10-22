// 작은 JSON 읽개 (네이티브 평가기 EcoV3Eval 전용 — 엔진 없이 표준 헤더만). 일 파일·두뇌 파일을 읽는다.
// 수는 strtod 로 읽는다: 파이썬 json 이 쓰는 float 는 가장 짧은 되돌림 십진이라 같은 double 로 돌아온다 (시작 상태를 비트 그대로 옮긴다).
// 큰 정수(PCG64 상태 128 비트)는 문자열로 받는다. 오류는 std::runtime_error (위치 포함).

#pragma once

#include <cstdint>
#include <cstdlib>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace MiniJson
{
	struct FValue
	{
		enum class EKind : std::uint8_t
		{
			Null,
			Bool,
			Number,
			String,
			Array,
			Object
		};
		EKind Kind = EKind::Null;
		bool B = false;
		double N = 0.0;
		std::string S;
		std::vector<FValue> A;
		std::vector<std::pair<std::string, FValue>> O;   // 적힌 순서 그대로

		bool IsNull() const { return Kind == EKind::Null; }
		bool IsObject() const { return Kind == EKind::Object; }
		bool IsArray() const { return Kind == EKind::Array; }

		const FValue* Find(const std::string& Key) const
		{
			if (Kind != EKind::Object)
			{
				return nullptr;
			}
			for (const auto& Kv : O)
			{
				if (Kv.first == Key)
				{
					return &Kv.second;
				}
			}
			return nullptr;
		}

		const FValue& At(const std::string& Key) const
		{
			const FValue* V = Find(Key);
			if (V == nullptr)
			{
				throw std::runtime_error("JSON 칸 '" + Key + "' 이 없다");
			}
			return *V;
		}

		double Num() const
		{
			if (Kind == EKind::Number)
			{
				return N;
			}
			if (Kind == EKind::Bool)
			{
				return B ? 1.0 : 0.0;
			}
			throw std::runtime_error("JSON 수가 아니다");
		}

		bool Bool() const
		{
			if (Kind == EKind::Bool)
			{
				return B;
			}
			if (Kind == EKind::Number)
			{
				return N != 0.0;
			}
			throw std::runtime_error("JSON 참·거짓이 아니다");
		}

		const std::string& Str() const
		{
			if (Kind != EKind::String)
			{
				throw std::runtime_error("JSON 문자열이 아니다");
			}
			return S;
		}

		const std::vector<FValue>& Arr() const
		{
			if (Kind != EKind::Array)
			{
				throw std::runtime_error("JSON 배열이 아니다");
			}
			return A;
		}

		double NumOr(const std::string& Key, double Def) const
		{
			const FValue* V = Find(Key);
			return (V == nullptr || V->IsNull()) ? Def : V->Num();
		}

		bool BoolOr(const std::string& Key, bool Def) const
		{
			const FValue* V = Find(Key);
			return (V == nullptr || V->IsNull()) ? Def : V->Bool();
		}

		std::string StrOr(const std::string& Key, const std::string& Def) const
		{
			const FValue* V = Find(Key);
			return (V == nullptr || V->Kind != EKind::String) ? Def : V->S;
		}
	};

	class FParser
	{
	public:
		explicit FParser(const std::string& Text) : T(Text) {}

		FValue Parse()
		{
			FValue V = Value();
			Ws();
			if (P != T.size())
			{
				Fail("값 뒤에 남은 글자가 있다");
			}
			return V;
		}

	private:
		const std::string& T;
		size_t P = 0;

		[[noreturn]] void Fail(const char* What) const
		{
			throw std::runtime_error(std::string("JSON 읽기 실패 (") + What + ") 위치 " + std::to_string(P));
		}

		void Ws()
		{
			while (P < T.size() && (T[P] == ' ' || T[P] == '\t' || T[P] == '\n' || T[P] == '\r'))
			{
				++P;
			}
		}

		bool Lit(const char* L)
		{
			size_t K = 0;
			while (L[K] != '\0')
			{
				if (P + K >= T.size() || T[P + K] != L[K])
				{
					return false;
				}
				++K;
			}
			P += K;
			return true;
		}

		static void PutUtf8(std::string& Out, std::uint32_t Cp)
		{
			if (Cp < 0x80)
			{
				Out += static_cast<char>(Cp);
			}
			else if (Cp < 0x800)
			{
				Out += static_cast<char>(0xC0 | (Cp >> 6));
				Out += static_cast<char>(0x80 | (Cp & 0x3F));
			}
			else if (Cp < 0x10000)
			{
				Out += static_cast<char>(0xE0 | (Cp >> 12));
				Out += static_cast<char>(0x80 | ((Cp >> 6) & 0x3F));
				Out += static_cast<char>(0x80 | (Cp & 0x3F));
			}
			else
			{
				Out += static_cast<char>(0xF0 | (Cp >> 18));
				Out += static_cast<char>(0x80 | ((Cp >> 12) & 0x3F));
				Out += static_cast<char>(0x80 | ((Cp >> 6) & 0x3F));
				Out += static_cast<char>(0x80 | (Cp & 0x3F));
			}
		}

		std::uint32_t Hex4()
		{
			if (P + 4 > T.size())
			{
				Fail("\\u 뒤 네 글자가 없다");
			}
			std::uint32_t V = 0;
			for (int k = 0; k < 4; ++k)
			{
				const char C = T[P++];
				V <<= 4;
				if (C >= '0' && C <= '9')
				{
					V |= static_cast<std::uint32_t>(C - '0');
				}
				else if (C >= 'a' && C <= 'f')
				{
					V |= static_cast<std::uint32_t>(C - 'a' + 10);
				}
				else if (C >= 'A' && C <= 'F')
				{
					V |= static_cast<std::uint32_t>(C - 'A' + 10);
				}
				else
				{
					Fail("\\u 의 16진이 아니다");
				}
			}
			return V;
		}

		std::string Str()
		{
			if (T[P] != '"')
			{
				Fail("문자열이 아니다");
			}
			++P;
			std::string Out;
			while (true)
			{
				if (P >= T.size())
				{
					Fail("문자열이 끝나지 않았다");
				}
				const char C = T[P++];
				if (C == '"')
				{
					break;
				}
				if (C != '\\')
				{
					Out += C;
					continue;
				}
				if (P >= T.size())
				{
					Fail("\\ 뒤가 없다");
				}
				const char E = T[P++];
				switch (E)
				{
				case '"': Out += '"'; break;
				case '\\': Out += '\\'; break;
				case '/': Out += '/'; break;
				case 'b': Out += '\b'; break;
				case 'f': Out += '\f'; break;
				case 'n': Out += '\n'; break;
				case 'r': Out += '\r'; break;
				case 't': Out += '\t'; break;
				case 'u':
				{
					std::uint32_t Cp = Hex4();
					if (Cp >= 0xD800 && Cp < 0xDC00 && P + 6 <= T.size() && T[P] == '\\' && T[P + 1] == 'u')
					{
						P += 2;
						const std::uint32_t Lo = Hex4();
						Cp = 0x10000 + ((Cp - 0xD800) << 10) + (Lo - 0xDC00);
					}
					PutUtf8(Out, Cp);
					break;
				}
				default: Fail("모르는 \\ 글자");
				}
			}
			return Out;
		}

		FValue Value()
		{
			Ws();
			if (P >= T.size())
			{
				Fail("값이 없다");
			}
			FValue V;
			const char C = T[P];
			if (C == '{')
			{
				V.Kind = FValue::EKind::Object;
				++P;
				Ws();
				if (P < T.size() && T[P] == '}')
				{
					++P;
					return V;
				}
				while (true)
				{
					Ws();
					std::string K = Str();
					Ws();
					if (P >= T.size() || T[P] != ':')
					{
						Fail("':' 가 없다");
					}
					++P;
					V.O.emplace_back(std::move(K), Value());
					Ws();
					if (P < T.size() && T[P] == ',')
					{
						++P;
						continue;
					}
					if (P < T.size() && T[P] == '}')
					{
						++P;
						break;
					}
					Fail("객체가 ',' 나 '}' 로 이어지지 않는다");
				}
				return V;
			}
			if (C == '[')
			{
				V.Kind = FValue::EKind::Array;
				++P;
				Ws();
				if (P < T.size() && T[P] == ']')
				{
					++P;
					return V;
				}
				while (true)
				{
					V.A.push_back(Value());
					Ws();
					if (P < T.size() && T[P] == ',')
					{
						++P;
						continue;
					}
					if (P < T.size() && T[P] == ']')
					{
						++P;
						break;
					}
					Fail("배열이 ',' 나 ']' 로 이어지지 않는다");
				}
				return V;
			}
			if (C == '"')
			{
				V.Kind = FValue::EKind::String;
				V.S = Str();
				return V;
			}
			if (Lit("true"))
			{
				V.Kind = FValue::EKind::Bool;
				V.B = true;
				return V;
			}
			if (Lit("false"))
			{
				V.Kind = FValue::EKind::Bool;
				V.B = false;
				return V;
			}
			if (Lit("null"))
			{
				return V;
			}
			// 수 (NaN·Infinity 는 파이썬 json 이 쓰지만 여기서는 받지 않는다 — 시작 상태에 없어야 한다)
			const char* Begin = T.c_str() + P;
			char* End = nullptr;
			const double D = std::strtod(Begin, &End);
			if (End == Begin)
			{
				Fail("값을 읽지 못했다");
			}
			P += static_cast<size_t>(End - Begin);
			V.Kind = FValue::EKind::Number;
			V.N = D;
			return V;
		}
	};

	inline FValue Parse(const std::string& Text)
	{
		FParser Pr(Text);
		return Pr.Parse();
	}
}
