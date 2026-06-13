# Plan-05: CrewAI多Agent独立角色重构

## 关联Schema
- **所属Phase**: Phase 2
- **依赖**: Plan-04 (动态Agent列表)
- **被依赖**: Plan-06, Plan-08, Plan-12
- **可并行**: Plan-07, Plan-09

## 目标
将CrewAI集成从"1个Dispatcher代理所有Agent"重构为"每个madcli Agent对应一个独立的CrewAI Agent角色"，真正发挥CrewAI多Agent协作能力。

## 涉及文件
- 主要修改: `madcli/crewai_adapter.py`
- 新增: `madcli/crewai_agent_factory.py`
- 测试文件: `tests/test_crewai_adapter.py`

## 具体改动

### 1. 为每个配置Agent创建CrewAI Agent
新增 `build_agent_crew(config)` 函数：
- 遍历 `config.agents`，为每个Agent创建独立的CrewAI Agent
- 每个Agent根据其角色获得不同的工具集（通过角色分类判断）

### 2. 角色分类
```python
def _classify_agent_role(agent_config: AgentConfig) -> str:
    """返回 'engineer' | 'reviewer' | 'planner'"""
```
根据Agent name和description中的关键词分类，决定赋予哪些工具。

### 3. 工具分配策略
- **engineer类**: run_madcli_agent_task + read_run_artifact
- **reviewer类**: read_run_artifact + 新增的diff检查工具
- **planner类**: run_madcli_agent_task + read_run_artifact + workflow状态查询

### 4. Manager Agent
- Manager不重复创建为Worker
- Manager的backstory中注入所有Worker Agent的能力描述
- Manager配备 `allow_delegation=True`

### 5. Crew构建
```python
worker_agents = [创建每个config agent对应的CrewAI Agent]
all_agents = [manager_agent] + worker_agents
crew = Crew(agents=all_agents, tasks=[delegation_task], process=Process.hierarchical, manager_agent=manager_agent)
```

## 测试要点
- N个配置Agent → N个Worker + 1个Manager CrewAI Agent
- 不同角色获得不同工具集
- 角色分类覆盖engineer/reviewer/planner三种
- Manager可委派给任一Worker
