"""기본 두뇌 헤더 (`export_weights_v3.py --default-brain` — 10-29 사용자 결정 '기본 두뇌 R7e로', 언리얼 `AI/Policy/EcoV3Brain.h` '기본 두뇌').

(1) 언리얼 모듈에 올린 `PolicyBrainV3Default.h` = 저장소 두뇌 파일(`AdaptiveEcosystem/EcoBrains/v3_r7_g995_s1_20m.json`)로 지금 코드가 만든 헤더 (바이트 단위 —
    두뇌 파일이 바뀌었는데 헤더를 다시 만들지 않았으면 여기서 걸린다),
(2) 헤더 배열을 다시 읽으면 두뇌 파일 바이트(줄 끝 LF)와 같고 상수(id·계약·관측·마스크 판·sha256·바이트 수)가 파일과 맞다,
(3) 두뇌 파일 줄 끝이 CRLF 여도(git core.autocrlf) 같은 헤더, 가중치를 바꾼 파일은 거부한다.
언리얼 쪽(같은 Parse 검사·파일과 같은 id·Play 시작 고르기)은 `Tests/EcoV3BrainTest.cpp` Brain.Default·`EcoPolicyV3IntegratedTest.cpp` Integrated.DefaultBrainStart.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

import export_weights_v3 as ex

HEADER = ex.UE_POLICY_DIR / ex.DEFAULT_BRAIN_HEADER
BRAIN = ex.DEFAULT_BRAIN_FILE

pytestmark = pytest.mark.skipif(not (HEADER.exists() and BRAIN.exists()), reason="언리얼 모듈 헤더·저장소 두뇌 파일이 필요하다")


def _lf(b: bytes) -> bytes:
    return b.replace(bytes([13, 10]), bytes([10]))


def _const(text: str, name: str) -> str:
    m = re.search(rf"inline constexpr [\w:* ]+ {name} = (.+?);", text)
    assert m, name
    return m.group(1).strip().strip('"')


def test_committed_header_is_current(tmp_path):
    info = ex.write_default_brain_header(BRAIN, tmp_path, ex.DEFAULT_BRAIN_LABEL)
    assert _lf((tmp_path / ex.DEFAULT_BRAIN_HEADER).read_bytes()) == _lf(HEADER.read_bytes()), \
        "PolicyBrainV3Default.h 가 지금 두뇌 파일·코드로 만든 것과 다르다 — python export_weights_v3.py --default-brain 로 다시 만든다"
    assert info["id"] == "v3_r7_g995_s1_20m@40d8710d" and info["label"] == "R7e"


def test_header_bytes_and_constants_match_brain_file():
    text = HEADER.read_text(encoding="utf-8")
    raw = _lf(BRAIN.read_bytes())
    d = json.loads(raw)
    body = text[text.index("kFile[kFileBytes] = {") :]
    body = body[body.index("\n") + 1 : body.index("};")]
    got = bytes(int(x) for x in re.findall(r"\d+", body))
    assert got == raw
    assert int(_const(text, "kFileBytes")) == len(raw)
    assert _const(text, "kFileSha256") == hashlib.sha256(raw).hexdigest()
    assert _const(text, "kBrainId") == d["id"] and _const(text, "kFileName") == BRAIN.name and _const(text, "kLabel") == "R7e"
    assert _const(text, "kContractHash") == d["contract_hash"] + "ULL" == "0xad7bad5e1acaf071ULL"
    assert int(_const(text, "kObsDim")) == d["obs_dim"] == 24 and int(_const(text, "kMaskVersion")) == d["mask_version"] == 5
    assert d["allowed"] == ["graze", "flee", "hide"]


def test_crlf_copy_same_header_and_bad_weights_refused(tmp_path):
    raw = _lf(BRAIN.read_bytes())
    crlf = tmp_path / BRAIN.name
    crlf.write_bytes(raw.replace(bytes([10]), bytes([13, 10])))
    a, _ = ex.default_brain_header_text(crlf, "R7e")
    b, _ = ex.default_brain_header_text(BRAIN, "R7e")
    cut = "#pragma once"
    assert a[a.index(cut):] == b[b.index(cut):]   # 머리 주석의 경로 줄만 다르고 상수·바이트는 같다 (줄 끝 무관)
    d = json.loads(raw)
    L = d["layers"][2]
    L["b_f32le_b64"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAA="   # 다른 바이트 (sha256 그대로)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        ex.default_brain_header_text(bad, "R7e")
    with pytest.raises(SystemExit):
        ex.default_brain_header_text(BRAIN, "R7e 기본")   # 이름표는 ASCII 글자·숫자·-·_
