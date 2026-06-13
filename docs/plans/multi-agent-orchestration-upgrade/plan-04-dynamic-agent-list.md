# Plan-04: 动态Agent列表消除硬编码

## 关联Schema
- **所属Phase**: Phase 1
- **依赖**: 无
- **被依赖**: Plan-05
- **可并行**: Plan-01, Plan-02, Plan-03, Plan-11

## 目标
消除 `planner.py` 中 `plan_tasks_with_agent()` 函数内硬编码的Agent列表，改为从配置动态读取。

## 涉及文件
- 主要修改: `madcli/planner.py`
- 测试文件: `tests/test_planner.py`

## 具体改动

### 1. Planner prompt动态化
当前prompt中写死:
```python
"agent": "strategy_engineer|codex_reviewer|claude_engineer"
```
改为动态从 `config.agents` 生成Agent选择列表，并附带每个Agent的description。

### 2. 更丰富的Agent信息注入
prompt中增加每个Agent的详细能力描述：
```
Available agents:
- "strategy_engineer": Implements strategy code using OpenCode. Runtime: opencode
- "codex_reviewer": Reviews diffs and reports using Codex. Runtime: codex
- "claude_engineer": Architecture design and implementation via Claude Code. Runtime: claude_code
```
这帮助规划Agent根据能力（不仅仅是名字）合理分配任务。

## 测试要点
- 自定义Agent列表出现在规划prompt中
- Agent描述信息被正确注入
- 新增/删除Agent后规划prompt自动更新
