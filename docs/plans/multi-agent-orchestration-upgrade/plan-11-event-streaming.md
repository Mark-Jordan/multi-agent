# Plan-11: 流式事件推送系统

## 关联Schema
- **所属Phase**: Phase 3 (但无依赖，可提前至Batch 1)
- **依赖**: 无
- **被依赖**: 无
- **可并行**: Plan-01, Plan-02, Plan-03, Plan-04

## 目标
将当前仅写文件的事件日志改为同时支持回调推送，让桌面应用能实时接收工作流进度。

## 涉及文件
- 新增: `madcli/event_bus.py`
- 修改: `madcli/workflow_store.py`, `madcli/run_store.py`, `madcli/orchestrator.py`
- 测试文件: `tests/test_event_bus.py`

## 具体改动

### 1. 事件总线
```python
class EventBus:
    """简单的发布-订阅事件总线，单例模式"""
    
    _instance = None
    
    def subscribe(self, event_type: str, callback: Callable) -> None
    def unsubscribe(self, event_type: str, callback: Callable) -> None
    def publish(self, event_type: str, payload: dict) -> None

# 预定义事件常量
WORKFLOW_STARTED = "workflow.started"
WORKFLOW_COMPLETED = "workflow.completed"
WORKFLOW_FAILED = "workflow.failed"
TASK_STARTED = "task.started"
TASK_COMPLETED = "task.completed"
TASK_FAILED = "task.failed"
TASK_RETRYING = "task.retrying"
TASK_BLOCKED = "task.blocked"
REVIEW_STARTED = "review.started"
REVIEW_COMPLETED = "review.completed"
HITL_REQUIRED = "hitl.required"
```

### 2. 集成方式
- 在 `WorkflowOrchestrator` 和 `WorkflowStore` 关键状态变更点同时调用 `store.append_event()` 和 `EventBus.publish()`
- 默认使用同步回调，不破坏现有CLI行为
- 支持异步回调用于流式场景

### 3. 桌面应用桥接
- Electron主进程可订阅EventBus事件
- 通过 `webContents.send()` 推送到渲染进程UI

## 测试要点
- 事件被正确发布到订阅者
- 取消订阅后不再收到事件
- 与现有文件日志不冲突
- 单例模式正常工作
