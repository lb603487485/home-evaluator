# Eval results — LLM ON

| # | segment | truth | estimate | error | conf | recovery@8 |
|---|---------|-------|----------|-------|------|------------|
| 1 | Evanston detached | $693,880 | $691,426 | -0.4% | B | 0% |
| 2 | Evanston detached | $558,930 | $539,397 | -3.5% | C | 12% |
| 3 | Evanston detached | $743,640 | $749,694 | +0.8% | B | 12% |
| 4 | Evanston townhouse | $426,598 | $414,823 | -2.8% | C | 50% |
| 5 | Tuscany detached | $607,159 | $655,319 | +7.9% | A | 0% |
| 6 | Tuscany detached | $637,758 | $640,221 | +0.4% | B | 0% |
| 7 | Tuscany detached | $675,759 | $714,619 | +5.8% | B | 0% |
| 8 | Auburn Bay detached | $793,458 | $776,596 | -2.1% | B | 0% |
| 9 | Auburn Bay detached | $870,507 | $870,545 | +0.0% | B | 0% |
| 10 | Auburn Bay townhouse | $368,146 | $369,503 | +0.4% | A | 25% |
| 11 | Killarney semi | $891,587 | $904,716 | +1.5% | A | 25% |
| 12 | Killarney semi | $743,442 | $758,772 | +2.1% | B | 38% |
| 13 | Killarney detached | $1,130,979 | $1,118,139 | -1.1% | B | 38% |
| 14 | Beltline apartment | $429,010 | $425,201 | -0.9% | B | 0% |
| 15 | Beltline apartment | $167,140 | $167,162 | +0.0% | B | 0% |
| 16 | Beltline apartment | $320,380 | $324,444 | +1.3% | B | 0% |
| 17 | Bridgeland apartment | $367,530 | $350,156 | -4.7% | B | 0% |
| 18 | Bridgeland townhouse | $455,158 | $476,823 | +4.8% | B | 25% |
| 19 | Aspen Woods detached | $1,921,788 | $1,915,150 | -0.3% | C | 25% |
| 20 | Bearspaw detached ◆ | $1,695,955 | $1,757,747 | +3.6% | C | 100% |

- **MAPE (all 20):** 2.2% · **MAPE (normal, n=18):** 2.2%
- **Median |error|:** 1.4%
- **Within ±10%:** 20/20
- **Mean comp-recovery@8 vs model-nearest-10:** 18%
- Scenario asserts passed: Bearspaw widened+flagged · non-arm's-length excluded · DATA_CONFLICT surfaced
- ◆ = search was widened

Recovery@8 note: similarity ranking optimizes adjusted-price reliability (distance, recency, attribute closeness), not raw value proximity, so low overlap with the value-nearest-10 is expected (chance ≈ 3%); estimate accuracy above is the outcome metric.
