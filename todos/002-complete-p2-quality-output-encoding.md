---
status: complete
priority: p2
issue_id: "002"
tags: [code-review, quality, windows, encoding]
dependencies: []
---

# 淇璐ㄩ噺闂ㄧ澶辫触浜х墿鐨?Windows 缂栫爜鑴嗗急鎬?
## Problem Statement

`quality` 鍛戒护鍦ㄧ埗杩涚▼涓浐瀹氱敤 UTF-8 瑙ｇ爜瀛愯繘绋嬭緭鍑猴紝浣嗘病鏈変繚璇佸瓙杩涚▼鏈韩涔熶互 UTF-8 鍐欏嚭銆傚綋鏌愪釜璐ㄩ噺闃舵澶辫触骞惰緭鍑轰腑鏂囨椂锛宍artifacts/quality/*-latest.txt` 鍙兘鍑虹幇涔辩爜锛岀洿鎺ュ墛寮辫鍒掍腑鈥滃け璐ュ弽棣堝彲璇烩€濆拰鈥淲indows 鐜涓枃鍏煎鈥濈殑鐩爣銆?
## Findings

- `paper_analysis/cli/quality.py:63` 鍒?`paper_analysis/cli/quality.py:73` 浣跨敤 `subprocess.run(... text=True, encoding="utf-8", errors="replace")` 鎹曡幏瀛愯繘绋嬭緭鍑恒€?- 杩欓噷娌℃湁璁剧疆 `PYTHONUTF8=1`銆乣PYTHONIOENCODING=utf-8` 鎴栧叾浠栧瓙杩涚▼缂栫爜绾︽潫銆?- 鍦ㄦ湰娆″疄鐜拌繃绋嬩腑锛宍artifacts/quality/typecheck-latest.txt` 鏇惧嚭鐜颁腑鏂囦贡鐮侊紝璇存槑澶辫触璺緞宸茬粡鍙楀奖鍝嶃€?- 娴嬭瘯浠ｇ爜閲屼负瀛愯繘绋嬫樉寮忚缃簡 UTF-8 鐜锛屼絾瀹為檯 `quality` CLI 娌℃湁閲囩敤鍚屾牱淇濇姢銆?
## Proposed Solutions

### Option 1: 璐ㄩ噺瀛愯繘绋嬬粺涓€娉ㄥ叆 UTF-8 鐜鍙橀噺

**Approach:** 鍦?`_run_stage()` 涓鍒剁幆澧冨苟璁剧疆 `PYTHONUTF8=1`銆乣PYTHONIOENCODING=utf-8`锛岀‘淇濇墍鏈?Python 瀛愬懡浠よ緭鍑虹ǔ瀹氫负 UTF-8銆?
**Pros:**
- 涓庣幇鏈夋祴璇曠瓥鐣ヤ竴鑷?- 瀹炵幇绠€鍗?- 鑳界洿鎺ヤ慨澶嶅け璐ヤ骇鐗╀贡鐮?
**Cons:**
- 涓昏瑕嗙洊 Python 瀛愯繘绋嬶紱鏈潵鑻ュ紩鍏ラ潪 Python 宸ュ叿杩橀渶鎵╁睍

**Effort:** 1 灏忔椂

**Risk:** Low

---

### Option 2: 鏀逛负浜岃繘鍒舵崟鑾峰悗鎸夌郴缁熺紪鐮佸洖閫€瑙ｇ爜

**Approach:** 璇诲彇鍘熷瀛楄妭娴侊紝浼樺厛 UTF-8锛屽け璐ユ椂鍥為€€鍒扮郴缁熼閫夌紪鐮侊紝鍐嶇粺涓€钀界洏涓?UTF-8銆?
**Pros:**
- 瀵规贩鍚堝伐鍏烽摼鏇寸ǔ鍋?- 鏇撮€傚悎鏈潵鎺ュ叆澶栭儴 lint/typecheck 宸ュ叿

**Cons:**
- 瀹炵幇鏇村鏉?- 闇€瑕侀澶栨祴璇曚笉鍚岀紪鐮佽矾寰?
**Effort:** 2-3 灏忔椂

**Risk:** Medium

---

### Option 3: 浠呮帴鍙楄嫳鏂囧け璐ヨ緭鍑?
**Approach:** 绾︽潫鎵€鏈夎川閲忚剼鏈彧杈撳嚭 ASCII/鑻辨枃锛屽洖閬跨紪鐮侀棶棰樸€?
**Pros:**
- 瀹炵幇鏈€绠€鍗?
**Cons:**
- 涓庘€滃敖鍙兘浣跨敤涓枃鈥濈殑浠撳簱鍘熷垯鍐茬獊
- 鐗虹壊鍙鎬?
**Effort:** < 1 灏忔椂

**Risk:** Medium

## Recommended Action

在 quality 子进程执行前统一注入 PYTHONUTF8=1 和 PYTHONIOENCODING=utf-8，并补一个单元测试锁定该环境约束。


## Technical Details

**Affected files:**
- `paper_analysis/cli/quality.py`
- `scripts/quality/lint.py`
- `scripts/quality/typecheck.py`
- `docs/engineering/testing-and-quality.md`

**Related components:**
- quality local-ci
- Windows terminal compatibility
- quality artifacts

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- **Review target:** current working tree on `main`
- **Evidence artifact:** `artifacts/quality/typecheck-latest.txt`
- **Related docs:** `docs/engineering/encoding-and-output.md`

## Acceptance Criteria

- [ ] 璐ㄩ噺闃舵瀛愯繘绋嬭緭鍑哄湪 Windows 涓嬬ǔ瀹氭寜 UTF-8 鎹曡幏
- [ ] 澶辫触 artifact 涓嶅啀鍑虹幇涓枃涔辩爜
- [ ] 澧炲姞鑷冲皯涓€涓鐩栧け璐ヨ矾寰勭紪鐮佺殑娴嬭瘯鎴栭獙璇佽剼鏈?- [ ] 鏂囨。鏇存柊杩愯鏃剁紪鐮佸亣璁?
## Work Log

### 2026-03-19 - Initial Discovery

**By:** Codex

**Actions:**
- 瀹℃煡浜?`quality` 瀛愯繘绋嬭皟鐢ㄩ€昏緫
- 瀵圭収娴嬭瘯浠ｇ爜鍙戠幇 UTF-8 鐜鍙湪娴嬭瘯閲岃缃紝鐢熶骇鍛戒护鏈缃?- 璁板綍浜嗕贡鐮?artifact 鐨勪慨澶嶆柟鍚?
**Learnings:**
- 褰撳墠 happy path 鑳介€氳繃锛屼絾澶辫触璺緞鐨勫彲璇绘€у湪 Windows 涓嬩笉绋冲畾
- 杩欎釜闂涓庝粨搴撶殑涓枃杈撳嚭鐩爣鐩存帴鐩稿叧

## Notes

- 璇ラ棶棰樹富瑕佸奖鍝嶅け璐ヨ瘖鏂紝涓嶅奖鍝嶆垚鍔熸墽琛岃矾寰勩€?
### 2026-03-19 - Resolved

**By:** Codex

**Actions:**
- 在 paper_analysis/cli/quality.py 中新增 uild_subprocess_env() 
- 为所有质量阶段子进程统一注入 UTF-8 环境变量
- 新增单元测试验证环境构造
- 重新运行 quality local-ci 确认通过

**Learnings:**
- Windows 下父进程按 UTF-8 解码并不够，必须同时约束子进程输出编码
