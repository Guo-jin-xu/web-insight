from pydantic import BaseModel, Field


class ActionModel(BaseModel):
    tool_name: str = Field(description="工具名称")
    tool_args: dict = Field(default_factory=dict, description="工具参数")


class AgentOutput(BaseModel):
    thinking: str = Field(default="", description="当前页面状态的分析思考")
    evaluation_previous_goal: str = Field(default="", description="上一步操作的成功/失败评估")
    memory: str = Field(default="", description="需要跨步骤记住的关键信息")
    next_goal: str = Field(default="", description="当前步骤的明确目标")
    action: list[ActionModel] = Field(default_factory=list, description="要执行的工具调用列表")

    @property
    def is_done(self) -> bool:
        return any(a.tool_name == "done" for a in self.action)


class BrowserStateHistory(BaseModel):
    url: str = ""
    title: str = ""
    tabs_count: int = 0
    interacted_element: str = ""
    screenshot_path: str | None = None


class AgentHistory(BaseModel):
    model_output: AgentOutput | None = None
    result: list = Field(default_factory=list)
    state: BrowserStateHistory | None = None


class AgentHistoryList(BaseModel):
    history: list[AgentHistory] = Field(default_factory=list)

    def final_result(self) -> str | None:
        if not self.history:
            return None
        last = self.history[-1]
        if last.model_output and last.model_output.is_done:
            for action in last.model_output.action:
                if action.tool_name == "done":
                    return action.tool_args.get("summary", "")
        return None

    def is_done(self) -> bool:
        if not self.history:
            return False
        last = self.history[-1]
        return last.model_output is not None and last.model_output.is_done


class AgentState(BaseModel):
    n_steps: int = 0
    consecutive_failures: int = 0
    last_model_output: AgentOutput | None = None
    last_result: list | None = None
    paused: bool = False
    stopped: bool = False
    session_initialized: bool = False