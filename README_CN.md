# 台风"巴威"(2026) 近实时韧性与脆弱性分析（中文说明）

**OASIS @ ACM SIGSPATIAL 2026 · Track A: Disaster Resilience & Vulnerability
Analysis 参赛项目。**

2026 年第 9 号超强台风"巴威"（国际编号 2609，峰值 910 hPa）预计于
2026-07-11 夜间在福建霞浦至浙江温岭一带登陆——本仓库在登陆前实时建立，
完整执行"灾前预测 → 灾后观测 → 韧性验证"闭环：

1. **Phase 1（登陆前，进行中）**：用实时路径快照（含 7/10/12 级风圈四象限
   半径与多机构预报）叠加人口格网、建筑轮廓与沿海低洼区，生成带时间戳的
   暴露度面与脆弱性观察名单——**灾前冻结，不做事后修改**；
2. **Phase 2（登陆后）**：跨视图损伤证据——卫星（Sentinel-1 SAR 优先，
   不受云影响）与街景/社会影像按逐样本可靠性门控仲裁，无法证实的单元
   显式输出 abstain + 待核查，而不是强行给标签；
3. **Phase 3（验证）**：瓦片优先级图 + 预算约束巡检路线 + **韧性记分卡**
   ——核心问题是"灾前结构在多大程度上预测了灾后损伤"，未命中与命中
   同等醒目地公布。

方法学基因来自 [CrossViewGate](https://github.com/rayford295/CrossViewGate)
（跨视图可靠性门控、空间分块评估、risk-aware 声明纪律，覆盖 2025 Eaton
野火与飓风 Ian/Milton 三个灾害）。

- 事件档案（含来源）：[`docs/event_bavi_2026.md`](docs/event_bavi_2026.md)
- 方法：[`docs/methodology.md`](docs/methodology.md)
- 赛道要求对齐：[`docs/track_a_alignment.md`](docs/track_a_alignment.md)
- 实时路径快照：`data/snapshots/`（浙江省水利厅台风 API，追加式存档）

```bash
pip install -e .
python scripts/fetch_bavi_track.py   # 抓取一次实时路径快照
python -m unittest discover -s tests
```

作者：杨一凡（Texas A&M University, Geography）。MIT License。
