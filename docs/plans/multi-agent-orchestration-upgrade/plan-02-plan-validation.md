# Plan-02: 计划验证与质量门禁

## 关联Schema
- **所属Phase**: Phase 1
- **依赖**: 无
- **被依赖**: Plan-07, Plan-09
- **可并行**: Plan-01, Plan-03, Plan-04, Plan-11

## 目标
在 `Planner.parse_planned_tasks()` 后增加逻辑验证层，检测循环依赖、不可达任务、Agent不存在等问题。

## 涉及文件
- 主要修改: `madcli/planner.py`
- 新增: `madcli/plan_validator.py`
- 测试文件: `tests/test_planner.py`

## 具体改动

### 1. 新增 `validate_plan(tasks, config) -> list[str]` 函数
在独立模块 `plan_validator.py` 中实现：
- **循环依赖检测**: 对 `depends_on` 做DFS环路检测
- **Agent存在性**: 每个task的agent字段必须在config.agents中存在
- **可达性验证**: 无孤立任务组
- **重复ID检测**: task_id不能重复
- **自依赖检测**: 任务不能依赖自身
- **审查Agent存在性**: review_by必须在config.agents中存在且非自身

### 2. 集成
- `parse_planned_tasks()` 调用后自动验证
- 验证失败给出清晰的错误信息，指出具体哪个任务有什么问题
- 在CLI中友好展示验证错误

## 测试要点
- 循环依赖被检测: A→B→C→A
- 缺失Agent被检测
- 重复task_id被检测
- 自依赖被检测
- 有效计划通过验证
