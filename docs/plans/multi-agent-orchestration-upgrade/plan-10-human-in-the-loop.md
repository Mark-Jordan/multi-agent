# Plan-10: 人在回路(HITL)机制

## 关联Schema
- **所属Phase**: Phase 3
- **依赖**: Plan-01 (并行执行)
- **被依赖**: 无
- **可并行**: Plan-06, Plan-08

## 目标
工作流关键节点支持暂停等待人工审批，审批通过后从暂停点继续执行。

## 涉及文件
- 修改: `madcli/workflow_store.py` (PlannedTask + WorkflowMetadata增加字段)
- 修改: `madcli/orchestrator.py` (暂停/恢复逻辑)
- 修改: `madcli/cli.py` (approve/reject/resume命令)
- 新增: `madcli/hitl.py` (HITL核心逻辑)
- 测试文件: `tests/test_hitl.py`

## 具体改动

### 1. PlannedTask新增字段
```python
require_approval: bool = False        # 执行前是否需要审批
require_review_approval: bool = False  # 审查后是否需要审批
approval_status: str | None = None     # None|pending|approved|rejected
approval_comment: str | None = None
```

### 2. HITL流程
```
任务执行前 → require_approval? → 暂停("awaiting_approval") → 等待
    ↓ approved
执行任务 → 审查完成 → require_review_approval? → 暂停 → 等待
    ↓ approved
继续下一任务
```

### 3. CLI命令
```bash
madcli workflow approve <workflow-id> <task-id> [--comment "..."]
madcli workflow reject <workflow-id> <task-id> [--reason "..."]
madcli workflow resume <workflow-id>
```

### 4. 暂停持久化
- 工作流状态设为 `"awaiting_approval"`
- 暂停点信息（哪个任务、什么审批类型）持久化到workflow.json
- resume时从暂停点恢复，跳过已审批任务

## 测试要点
- require_approval任务在执行前暂停
- approve后继续执行
- reject后标记失败
- resume从未完成点继续
- 审批状态正确持久化
