# SCHEMA: 多Agent自主协作系统升级

> 本文件为Schema总计划，定义整体目标、架构、子计划依赖关系和执行顺序。
> 各子计划详情见同目录下的 `plan-NN-*.md` 文件。

---

## 一、总目标

将 `multi-agent-dev-cli` 的多Agent自主协作能力从"基础可用但不完善"提升至接近主流多Agent编排系统水平。核心指标：支持真正的多Agent并行协作、动态工作流适配、Agent间结构化通信、人在回路。

## 二、文件组织结构

```
docs/plans/multi-agent-orchestration-upgrade/
├── SCHEMA.md                            # 本文件 - 总计划
├── plan-01-parallel-execution.md        # 子计划1
├── plan-02-plan-validation.md           # 子计划2
├── plan-03-retry-and-fallback.md        # 子计划3
├── plan-04-dynamic-agent-list.md        # 子计划4
├── plan-05-crewai-multi-agent-roles.md  # 子计划5
├── plan-06-agent-communication.md       # 子计划6
├── plan-07-dynamic-replan.md            # 子计划7
├── plan-08-manager-tools.md             # 子计划8
├── plan-09-acceptance-criteria.md       # 子计划9
├── plan-10-human-in-the-loop.md         # 子计划10
├── plan-11-event-streaming.md           # 子计划11
├── plan-12-crewai-flow-backend.md       # 子计划12
└── plan-13-workflow-templates.md        # 子计划13
```

## 三、整体架构（目标态）

```
用户/桌面应用
    ↓
madcli CLI (cli.py)
    ↓
┌─────────────────────────────────────────────────────────────┐
│                      编排协调层                              │
│                                                             │
│  Planner          Orchestrator         CrewAI Adapter       │
│  ├─ 计划生成      ├─ 拓扑并行调度      ├─ 多Agent独立角色    │
│  ├─ 计划验证      ├─ 重试/降级策略     ├─ Agent间通信协议    │
│  └─ 动态重规划    ├─ HITL暂停/恢复     └─ Manager直接工具    │
│                   └─ 验收自动评估                            │
│                                                             │
│        共用基础: TaskRunner | WorkflowStore | Executors      │
└─────────────────────────────────────────────────────────────┘
```

## 四、子计划依赖关系图

```
Phase 1 (Batch 1 — 可5路并行，互不依赖)
├── Plan-01: 并行任务执行引擎          [无依赖]
├── Plan-02: 计划验证与质量门禁        [无依赖]
├── Plan-03: 任务失败重试与降级策略    [无依赖]
├── Plan-04: 动态Agent列表消除硬编码   [无依赖]
└── Plan-11: 流式事件推送系统          [无依赖]

Phase 2 (Batch 2 — 可3路并行)
├── Plan-05: CrewAI多Agent独立角色重构 [依赖 Plan-04]
├── Plan-07: 动态重规划引擎            [依赖 Plan-01, Plan-02]
└── Plan-09: 任务验收标准与自动评估    [依赖 Plan-02]

Phase 3 (Batch 3 — 可3路并行)
├── Plan-06: Agent间结构化通信协议     [依赖 Plan-05]
├── Plan-08: Manager Agent工具集       [依赖 Plan-05]
└── Plan-10: 人在回路(HITL)机制        [依赖 Plan-01]

Phase 4 (Batch 4 — 可2路并行)
├── Plan-12: CrewAI Flow状态机后端     [依赖 Plan-05]
└── Plan-13: 工作流模板库              [依赖 Plan-07, Plan-09]
```

## 五、每个子计划的摘要

| 编号 | 子计划 | 涉及模块 | 改动量 | 核心文件 |
|------|--------|---------|--------|---------|
| 01 | 并行任务执行引擎 | orchestrator | 中 | `orchestrator.py` |
| 02 | 计划验证 | planner | 小 | `planner.py` (+新增 validator) |
| 03 | 重试与降级 | orchestrator, task_runner | 中 | `orchestrator.py`, `task_runner.py` |
| 04 | 动态Agent列表 | planner | 小 | `planner.py` |
| 05 | CrewAI多Agent角色 | crewai_adapter | 大 | `crewai_adapter.py` (+新增 factory) |
| 06 | Agent通信协议 | orchestrator, task_runner | 中 | `orchestrator.py` (+新增 message模块) |
| 07 | 动态重规划引擎 | orchestrator, planner | 中 | `orchestrator.py`, `planner.py` |
| 08 | Manager工具集 | crewai_adapter | 小 | `crewai_adapter.py` |
| 09 | 验收标准与评估 | orchestrator, planner | 小 | `orchestrator.py`, `workflow_store.py` |
| 10 | 人在回路 | orchestrator, cli | 中 | `orchestrator.py` (+新增 hitl模块) |
| 11 | 流式事件推送 | store, orchestrator | 小 | (+新增 event_bus模块) |
| 12 | CrewAI Flow后端 | crewai_adapter, cli | 中 | (+新增 flow_backend模块) |
| 13 | 工作流模板库 | cli | 中 | (+新增 templates模块+目录) |

## 六、执行策略

1. **优先Batch 1**（5个子计划无依赖，可开5个Agent同时推进）
2. Batch 1全部完成后，**Batch 2的3个子计划并行**
3. Batch 2全部完成后，**Batch 3的3个子计划并行**
4. 最后**Batch 4的2个子计划并行**

## 七、验证

每个子计划：运行该模块单元测试 + 全量回归 `python -m unittest discover -s tests -v`
全部完成后：端到端dry-run（多Agent并行+审查+重试+HITL全链路）
