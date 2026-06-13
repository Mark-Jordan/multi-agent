# Plan-13: 工作流模板库

## 关联Schema
- **所属Phase**: Phase 4
- **依赖**: Plan-07 (动态重规划), Plan-09 (验收标准)
- **被依赖**: 无
- **可并行**: Plan-12

## 目标
预定义常见多Agent协作模式的工作流模板，用户通过 `--template` 参数一键使用。

## 涉及文件
- 新增: `madcli/workflow_templates.py`
- 新增: `madcli/templates/` 目录及JSON模板文件
- 修改: `madcli/cli.py` (workflow run --template)
- 测试文件: `tests/test_workflow_templates.py`

## 具体改动

### 1. 预定义模板

| 模板名 | 流程 | 适用场景 |
|--------|------|---------|
| `implement-review` | 实现→审查→修复→再审查 | 功能开发 |
| `research-plan-implement` | 调研→方案→实施→验证 | 技术探索 |
| `refactor-verify` | 重构→测试→审查→回滚预案 | 代码重构 |
| `multi-perspective-review` | 多Agent并行审查→综合报告 | 代码评审 |
| `debug-fix-verify` | 诊断→修复→测试→回归 | Bug修复 |

### 2. 模板格式 (JSON)
```json
{
  "name": "implement-review",
  "description": "Standard implement-then-review workflow",
  "tasks": [
    {
      "id": "implement",
      "agent": "{{engineer}}",
      "task": "{{task}}",
      "acceptance_criteria": ["Tests pass"],
      "review_by": "{{reviewer}}"
    }
  ]
}
```

### 3. CLI集成
```bash
madcli workflow run "Add login API" --template implement-review \
    --var engineer=strategy_engineer --var reviewer=codex_reviewer
```

### 4. 自定义模板目录
支持 `--templates-dir` 加载用户自定义模板

## 测试要点
- 内置模板可正确加载和解析
- 变量替换正确
- 生成的计划通过验证
- 自定义模板目录支持
