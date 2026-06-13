# Plan-01: 并行任务执行引擎

## 关联Schema
- **所属Phase**: Phase 1
- **依赖**: 无
- **被依赖**: Plan-07, Plan-10
- **可并行**: Plan-02, Plan-03, Plan-04, Plan-11

## 目标
让 `WorkflowOrchestrator.run_plan()` 支持拓扑排序级别的并行执行，同一层内无依赖关系的任务并发运行。

## 涉及文件
- 主要修改: `madcli/orchestrator.py`
- 测试文件: `tests/test_orchestrator.py`

## 具体改动

### 1. 拓扑排序分层
在 `run_plan()` 方法中增加 `_topological_layers(tasks)` 方法：
- 输入: `list[PlannedTask]`
- 输出: `list[list[PlannedTask]]` — 每层内部的任务无相互依赖，可并行
- 依赖解析基于 `depends_on` 字段
- 未指定依赖的任务归入第一层

### 2. 并发执行
使用 `concurrent.futures.ThreadPoolExecutor` 执行每层内的任务：
- 默认最大并发数: `max_workers=4`（可配置）
- 每层内的任务提交为 future，全部完成后收集结果再进入下一层
- 任一任务失败，根据 `allow_failure` 决定是否继续同层其他任务

### 3. 线程安全
- `WorkflowStore` 的写入操作加 `threading.Lock`
- `RunStore` 同理确保线程安全

### 4. 配置项
在 `AppConfig` 中增加 `max_parallel_workers: int = 4`

## 测试要点
- 3个独立任务应并发执行（验证不严格串行）
- 有依赖链的任务应分层执行
- 并行层中一个任务失败，同层其他无依赖任务继续
- 线程安全不出现数据竞争
