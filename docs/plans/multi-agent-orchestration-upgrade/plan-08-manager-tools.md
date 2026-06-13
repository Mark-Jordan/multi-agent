# Plan-08: Manager Agent工具集

## 关联Schema
- **所属Phase**: Phase 3
- **依赖**: Plan-05 (CrewAI多Agent角色)
- **被依赖**: 无
- **可并行**: Plan-06, Plan-10

## 目标
为CrewAI Manager Agent配备直接工具，使其能直接检查进展、读取产物，而不只是盲目委派。

## 涉及文件
- 主要修改: `madcli/crewai_adapter.py`
- 测试文件: `tests/test_crewai_adapter.py`

## 具体改动

### 1. 新增Manager工具

| 工具名 | 功能 | 用途 |
|--------|------|------|
| `list_worker_agents` | 列出所有可用的Worker Agent | 让Manager了解有哪些工人可用 |
| `check_workflow_status` | 查看当前工作流所有任务状态 | 进度监控 |
| `get_task_detail` | 获取指定任务的详细信息和产物路径 | 深入检查 |
| `summarize_progress` | 汇总工作流完成/失败/待处理统计 | 快速评估 |

### 2. 工具分配
- Manager Agent获得全部管理类工具
- Manager保持 `allow_delegation=True`
- Manager prompt中注入何时用工具检查、何时委派给Worker的决策指导

### 3. 决策增强
在Manager的goal/backstory中明确指导：
- "先用 check_workflow_status 查看全局进度"
- "遇到问题时先读取相关产物，再决定是修复还是重做"
- "根据进度动态调整后续任务分配"

## 测试要点
- Manager Agent拥有管理工具
- 工具可被正确调用（mock环境）
- Manager能读取运行产物做决策
