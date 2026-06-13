# Plan-03: 任务失败重试与降级策略

## 关联Schema
- **所属Phase**: Phase 1
- **依赖**: 无
- **被依赖**: 无
- **可并行**: Plan-01, Plan-02, Plan-04, Plan-11

## 目标
单Agent任务执行失败时支持自动重试和降级策略，不直接标记整个工作流失败。

## 涉及文件
- 修改: `madcli/task_runner.py`, `madcli/orchestrator.py`
- 数据模型: `madcli/workflow_store.py` (PlannedTask增加字段)
- 测试文件: `tests/test_orchestrator.py`, `tests/test_cli.py`

## 具体改动

### 1. PlannedTask 新增字段
```python
retry_count: int = 0          # 最大重试次数，0=不重试
retry_delay: float = 5.0      # 重试间隔秒数
fallback_task_id: str | None = None  # 失败后的降级替代任务
allow_failure: bool = False    # 是否允许失败不阻塞工作流
```
注意：为保持向后兼容，这些字段都设默认值。

### 2. Orchestrator 重试逻辑
- 任务失败后检查 `retry_count`，未达上限则等待 `retry_delay` 后重试
- 重试耗尽后检查 `fallback_task_id`，执行降级任务
- `allow_failure=True` 的任务失败不标记工作流失败
- 重试时复用相同 AgentTaskRequest

### 3. TaskRunner 增强
- 增加 `retry_attempt` 记录到 run metadata
- 重试时在相同 run_id 目录下追加attempt事件

## 测试要点
- 重试耗尽后标记失败
- 降级任务被正确触发
- allow_failure任务失败不阻塞工作流
- 重试间隔生效
