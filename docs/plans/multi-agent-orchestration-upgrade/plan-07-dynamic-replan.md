# Plan-07: 动态重规划引擎

## 关联Schema
- **所属Phase**: Phase 2
- **依赖**: Plan-01 (并行执行), Plan-02 (计划验证)
- **被依赖**: Plan-13
- **可并行**: Plan-05, Plan-09

## 目标
任务失败或产生意外结果时，允许planner重新评估并生成新计划，而非直接终止工作流。

## 涉及文件
- 主要修改: `madcli/orchestrator.py`
- 修改: `madcli/planner.py`
- 测试文件: `tests/test_orchestrator.py`

## 具体改动

### 1. Re-plan触发条件
- 任务执行失败（`ok=False`）且 `allow_failure=False`
- 任务审查状态为 "review_failed"
- 用户通过HITL主动触发re-plan

### 2. Re-plan上下文
调用 `plan_tasks_with_agent()` 时注入：
- 已完成任务的摘要（task_id + 状态 + handoff summary）
- 失败任务的错误信息
- 剩余待执行任务列表
- 原始目标描述

### 3. 计划合并逻辑
- Re-plan返回的新任务列表替换所有未执行的任务
- 已完成任务保持不变（保留run_id和状态）
- 新任务需通过 plan-02 的验证

### 4. 安全限制
- 最大re-plan次数: `max_replans: int = 3`
- 超过限制后标记工作流失败并给出原因

## 测试要点
- 任务失败后触发re-plan
- 新任务替换未执行的旧任务
- 已完成任务不受影响
- 超过最大re-plan次数后正确终止
