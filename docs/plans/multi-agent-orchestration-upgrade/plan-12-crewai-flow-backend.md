# Plan-12: CrewAI Flow状态机后端

## 关联Schema
- **所属Phase**: Phase 4
- **依赖**: Plan-05 (CrewAI多Agent角色)
- **被依赖**: 无
- **可并行**: Plan-13

## 目标
增加基于CrewAI Flow的确定性状态机后端，支持需要可靠状态转换的复杂工作流场景。

## 涉及文件
- 新增: `madcli/crewai_flow_backend.py`
- 修改: `madcli/crewai_adapter.py`, `madcli/cli.py`
- 测试文件: `tests/test_crewai_flow_backend.py`

## 具体改动

### 1. 状态定义
```
START → PLAN_READY → TASK_DISPATCHING → TASK_RUNNING
    ├── TASK_SUCCEEDED → (下一任务 或) ALL_DONE
    ├── TASK_FAILED → (重试 或) ERROR
    └── REVIEW_REQUIRED → REVIEW_RUNNING
        ├── REVIEW_PASSED → (下一任务 或) ALL_DONE
        └── REVIEW_FAILED → (重规划 或) ERROR
```

### 2. Flow实现
使用CrewAI Flow API定义状态机和转换条件。每个状态对应一个处理函数。

### 3. CLI集成
```bash
madcli workflow run <goal> --backend crewai-flow --plan-file <json>
```
Flow后端适用于需要确定性执行、可审计、可恢复的工作流。

## 测试要点
- 状态机从START走到ALL_DONE
- 任务失败时进入ERROR
- 审查失败时根据配置进入重规划或ERROR
- 状态可在持久化后恢复
