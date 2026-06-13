# Plan-06: Agent间结构化通信协议

## 关联Schema
- **所属Phase**: Phase 3
- **依赖**: Plan-05 (CrewAI多Agent角色)
- **被依赖**: 无
- **可并行**: Plan-08, Plan-10

## 目标
设计Agent间消息/产物传递协议，让上游任务的输出能结构化地传递给下游任务，而非仅靠文件路径传递。

## 涉及文件
- 新增: `madcli/agent_message.py`
- 修改: `madcli/orchestrator.py`, `madcli/task_runner.py`
- 测试文件: `tests/test_agent_message.py`

## 具体改动

### 1. 消息数据模型
```python
@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    from_task_id: str
    to_task_id: str | None  # None = 广播给所有下游
    message_type: str       # 'handoff'|'review_request'|'result'|'info'
    content: str
    artifact_paths: list[str]
    created_at: str

@dataclass(frozen=True)
class TaskHandoff:
    """Worker→下游的结构化交接包"""
    source_task_id: str
    source_run_id: str
    summary: str            # 任务完成摘要
    key_files: list[str]    # 关键文件路径
    findings: str           # 关键发现
    warnings: str           # 注意事项
    suggestions: str        # 给后续任务的建议
```

### 2. 消息存储
- 存放在 `workflow_dir/handoffs/` 目录
- 每个handoff一个JSON文件
- 下游任务启动时自动将上游handoff注入context_files

### 3. Orchestrator集成
- 任务完成后自动生成 `TaskHandoff`
- 下游任务context自动包含所有上游任务的handoff
- 支持手动指定需要传递的特定产物

## 测试要点
- 任务完成后自动生成Handoff
- 下游任务context包含上游handoff
- 消息持久化到正确路径
- 多上游依赖时所有handoff都被注入
