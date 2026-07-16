# DisasterPilot（中文说明）

**从公开灾害信息到可审计决策的多智能体流水线——覆盖灾前监测到灾后证据的
完整生命周期的可审计骨架。**

🌐 **网站：https://rayford295.github.io/DisasterPilot/**

OASIS @ ACM SIGSPATIAL 2026 · Track A 参赛项目。首个实战案例：**2026 年
第 9 号台风"巴威"**——本流水线在其登陆闽浙沿海之前开始实时捕获，并保留了
独立的事件结案记录。

## 五个智能体角色

| 角色 | 职责 | 状态 |
| --- | --- | --- |
| **Watcher** | 轮询公开数据源、注册事件、追加式快照存档 | ✅ 实装（浙江水利厅台风 API） |
| **Dossier** | 从捕获数据生成机器可验证的结构化事件档案 | ✅ 实装 |
| **Exposure** | 风圈扫掠面 × 人口/建筑 → 暴露度与脆弱性观察名单 | ✅ 几何层实装 |
| **Evidence** | 跨视图损伤评估（可靠性门控，无影像时拒绝输出） | 接口冻结，灾后激活 |
| **Decision** | 观察通报 → 瓦片优先级 → 巡检路线 → 韧性记分卡 | ✅ 仅通报阶段实装 |

三条让它区别于 demo 的设计规则：

1. **追加式产物 + 完整溯源**：每个产物带智能体名、UTC 时间戳、输入清单；
   灾前产物被冻结，灾后验证天然诚实；
2. **fail-closed**：没有影像就没有损伤数字，缺输入就记录失败，绝不静默跳过；
3. **显式未知**：每份决策产物把"不知道什么"列得和"知道什么"一样醒目。

证据方法学来自 [CrossViewGate](https://github.com/rayford295/CrossViewGate)
研究线（跨视图可靠性门控，已在 Eaton 野火与飓风 Ian/Milton 验证）。

## 巴威结案案例

- `events/bavi-2026/snapshots/`：41 份追加式路径快照，最终源数据标记台风
  已结束，含 168 个路径点和 7/10/12 级风圈四象限半径；
- `events/bavi-2026/DOSSIER.md`：带来源的事件档案 + 灾后核对台账；
- `events/bavi-2026/{dossier,exposure,decision}/`：流水线产物。
- `events/bavi-2026/closure/`：独立的结案记录，保存源端报告的两次浙江登陆，
  不改写冻结的灾前产物。

结案不等于灾后评估完成：官方最佳路径核对、人口/建筑暴露统计、灾后影像损伤
证据与观察名单验证均明确标记为待完成，不能由本仓库现有数据推断。

```bash
pip install -e .
python scripts/run_pre_event.py --event-id bavi-2026 --tfid 202609 --offline
python scripts/close_event.py --event-dir events/bavi-2026
python -m unittest discover -s tests
```

架构详见 [`docs/architecture.md`](docs/architecture.md)。
作者：杨一帆（Texas A&M University, Geography）。MIT License。
