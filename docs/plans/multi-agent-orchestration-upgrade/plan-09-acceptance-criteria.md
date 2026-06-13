# Plan-09: 任务验收标准与自动评估

## 关联Schema
- **所属Phase**: Phase 2
- **依赖**: Plan-02 (计划验证)
- **被依赖**: Plan-13
- **可并行**: Plan-05, Plan-07

## 目标
为每个 `PlannedTask` 增加验收标准字段，Worker完成后由审查Agent自动评估是否达标。

## 涉及文件
- 修改: `madcli/workflow_store.py` (PlannedTask字段)
- 修改: `madcli/orchestrator.py` (评估逻辑)
- 修改: `madcli/planner.py` (规划时生成验收标准)
- 测试文件: `tests/test_orchestrator.py`, `tests/test_planner.py`

## 具体改动

### 1. PlannedTask新增字段
```python
acceptance_criteria: list[str] | None = None  # 验收标准列表
auto_evaluate: bool = True                     # 是否自动评估
evaluation_score: float | None = None          # 0.0-1.0
evaluation_summary: str | None = None          # 评估总结
```
所有新字段设默认值保证向后兼容。

### 2. 评估流程
- Worker完成后，将验收标准注入审查Agent的context
- 审查Agent在review时同时评估是否满足验收标准
- 评分低于阈值（默认0.6）标记 `review_failed`
- 评估结果写入 `evaluation_score` 和 `evaluation_summary`

### 3. Planner生成验收标准
- 在规划prompt中要求Agent为每个任务生成1-3条可验证的验收标准
- 验收标准应具体、可验证（例如"所有测试通过"而非"代码质量好"）
- 无验收标准时向后兼容，不强制要求

## 测试要点
- 验收标准被正确解析和存储
- 审查Agent收到包含验收标准的context
- 低分任务被标记为review_failed
- 无验收标准时不报错
