---
status: complete
priority: p2
issue_id: "001"
tags: [code-review, quality, cli, reliability]
dependencies: []
---

# 涓轰笟鍔?CLI 澧炲姞缁撴瀯鍖栬緭鍏ラ敊璇鐞?
## Problem Statement

褰撳墠 `conference` 鍜?`arxiv` 鍛戒护鍦ㄨ緭鍏ユ枃浠朵笉瀛樺湪銆丣SON 闈炴硶鎴栫粨鏋勪笉鍖归厤鏃朵細鐩存帴鎶?Python traceback锛岃€屼笉鏄繑鍥炲彲璇汇€佸彲鎿嶄綔鐨?CLI 澶辫触淇℃伅銆傝繖浼氱牬鍧忚鍒掗噷瑕佹眰鐨勨€滅粨鏋勫寲鏂囨湰杈撳嚭鈥濆拰闈㈠悜缁堢鐢ㄦ埛鐨勭ǔ瀹氬懡浠ら潰銆?
## Findings

- `paper_analysis/shared/sample_loader.py:10` 鍜?`paper_analysis/shared/sample_loader.py:15` 鐩存帴璋冪敤 `Path.read_text()` 涓?`json.loads()`锛屾病鏈変换浣曞紓甯歌浆鎹€?- `paper_analysis/cli/conference.py:36` 鍜?`paper_analysis/cli/arxiv.py:36` 鐩存帴璋冪敤 pipeline锛屾湭鎹曡幏 `FileNotFoundError`銆乣JSONDecodeError` 鎴栨暟鎹粨鏋勯敊璇€?- 澶嶇幇鍛戒护锛歚py -m paper_analysis.cli.main conference filter --input missing.json`銆?- 瀹為檯缁撴灉鏄畬鏁?traceback锛岃€屼笉鏄被浼?`[FAIL] ... summary: ... next: ...` 鐨勭敤鎴峰彲娑堣垂杈撳嚭銆?
## Proposed Solutions

### Option 1: 鍦?CLI 灞傜粺涓€鎹曡幏骞舵牸寮忓寲寮傚父

**Approach:** 鍦?`conference` / `arxiv` handler 涓崟鑾峰父瑙佽緭鍏ュ紓甯革紝缁熶竴杈撳嚭缁撴瀯鍖栧け璐ユ枃鏈苟杩斿洖闈為浂閫€鍑虹爜銆?
**Pros:**
- 淇敼鑼冨洿灏?- 淇濇寔 loader 鍜?service 灞傜畝鍗?- 鏈€璐磋繎鐢ㄦ埛鍙鍏ュ彛

**Cons:**
- 涓や釜涓氬姟鍛藉悕绌洪棿闇€瑕佸叡浜竴濂楅敊璇牸寮忓寲閫昏緫
- 濡傛灉鍚庣画鍏ュ彛澧炲锛屽鏄撻噸澶?
**Effort:** 1-2 灏忔椂

**Risk:** Low

---

### Option 2: 鍦ㄥ叡浜姞杞藉眰瀹氫箟棰嗗煙閿欒绫诲瀷

**Approach:** 鍦?`sample_loader` 涓妸鏂囦欢缂哄け銆丣SON 閿欒鍜?schema 閿欒杞崲涓鸿嚜瀹氫箟寮傚父锛屽啀鐢?CLI 灞傜粺涓€娓叉煋銆?
**Pros:**
- 鍒嗗眰娓呮櫚
- 鍚庣画鎵╁睍鍒版洿澶氭潵婧愭椂鏇翠竴鑷?
**Cons:**
- 闇€瑕佹柊澧炲紓甯告ā鍨嬪拰娴嬭瘯
- 鍒濇湡瀹炵幇姣?Option 1 绋嶉噸

**Effort:** 2-4 灏忔椂

**Risk:** Low

---

### Option 3: 鍙湪鏂囨。涓０鏄庤緭鍏ヨ姹?
**Approach:** 淇濇寔浠ｇ爜涓嶅彉锛屽彧鍦?README 鍜屽府鍔╂枃鏈腑寮鸿皟杈撳叆鏂囦欢蹇呴』瀛樺湪涓斿悎娉曘€?
**Pros:**
- 闆朵唬鐮佹敼鍔?
**Cons:**
- 鏃犳硶瑙ｅ喅鐪熷疄宕╂簝
- 涓嶆弧瓒崇ǔ瀹?CLI 鐨勭洰鏍?
**Effort:** < 1 灏忔椂

**Risk:** High

## Recommended Action

在共享加载层抛出 CliInputError，并在 conference / rxiv CLI handler 中统一格式化失败输出；同时补 integration test 防止回归。


## Technical Details

**Affected files:**
- `paper_analysis/shared/sample_loader.py`
- `paper_analysis/cli/conference.py`
- `paper_analysis/cli/arxiv.py`
- `tests/integration/`

**Related components:**
- ConferencePipeline
- ArxivPipeline
- CLI command surface

**Database changes (if any):**
- Migration needed? No
- New columns/tables? None

## Resources

- **Review target:** current working tree on `main`
- **Reproduction:** `py -m paper_analysis.cli.main conference filter --input missing.json`
- **Documentation:** `docs/engineering/testing-and-quality.md`

## Acceptance Criteria

- [ ] `conference` / `arxiv` 鍦ㄨ緭鍏ユ枃浠剁己澶辨椂杩斿洖缁撴瀯鍖栭敊璇枃鏈€岄潪 traceback
- [ ] 闈炴硶 JSON 鍜?schema 閿欒涔熸湁绋冲畾閿欒杈撳嚭
- [ ] 澧炲姞瑕嗙洊鍧忚緭鍏ュ満鏅殑 integration tests
- [ ] 甯姪鏂囨湰鎴栨枃妗ｈ鏄庡け璐ヨ涔?
## Work Log

### 2026-03-19 - Initial Discovery

**By:** Codex

**Actions:**
- 瀹℃煡浜?`sample_loader` 涓?CLI handler 鐨勫紓甯歌矾寰?- 澶嶇幇浜嗙己澶辫緭鍏ユ枃浠跺鑷寸殑 traceback
- 璁板綍浜嗗彲琛屼慨澶嶆柟妗?
**Learnings:**
- 褰撳墠 CLI happy path 鍙敤锛屼絾寮傚父璺緞瀹屽叏鏆撮湶搴曞眰瀹炵幇缁嗚妭
- 闇€瑕佹妸杈撳叆閿欒鎻愬崌涓虹ǔ瀹氱殑鐢ㄦ埛鎺ュ彛璇箟

## Notes

- 璇ラ棶棰樹笉闃诲 happy path锛屼絾浼氬奖鍝嶄换浣曠湡瀹炵敤鎴疯緭鍏ラ敊璇満鏅€?
### 2026-03-19 - Resolved

**By:** Codex

**Actions:**
- 新增 paper_analysis/cli/common.py 统一输入异常与失败输出
- 在 sample_loader 中把文件缺失、JSON 错误和 schema 错误转换为 CliInputError`r
- 为 conference / rxiv 增加结构化错误返回
- 新增缺失输入的 integration test

**Learnings:**
- 共享异常 + CLI 渲染的分层方式最适合这个仓库当前阶段
- 这样能保持 service 层干净，同时让终端语义稳定
