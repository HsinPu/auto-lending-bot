from dataclasses import dataclass


@dataclass(frozen=True)
class RunStepDefinition:
    key: str
    label: str
    description: str


RUN_STEP_DEFINITIONS = (
    RunStepDefinition(
        key="create-run",
        label="建立本次執行紀錄",
        description="建立這一輪 run，後續用來追蹤成功、失敗與建立委託數。",
    ),
    RunStepDefinition(
        key="sync-active-loans",
        label="同步放貸中資料",
        description="讀取目前已成交、正在放貸中的資料並更新本地快照。",
    ),
    RunStepDefinition(
        key="detect-new-active-loans",
        label="檢查新成交放貸",
        description="比對上一輪與這一輪的放貸中資料，必要時發送成交通知。",
    ),
    RunStepDefinition(
        key="sync-balances",
        label="讀取 Lending 可用餘額",
        description="讀取 Funding/Lending wallet 裡可拿來放貸的幣種與金額。",
    ),
    RunStepDefinition(
        key="sync-open-offers",
        label="檢查未成交委託",
        description="視設定同步目前還掛在市場上的未成交委託。",
    ),
    RunStepDefinition(
        key="rebalance-open-offers",
        label="處理舊委託",
        description="視設定決定是否保留或取消不符合策略的舊委託。",
    ),
    RunStepDefinition(
        key="load-market-orders",
        label="讀取市場利率",
        description="逐幣別讀取 lending order book，確認目前市場利率。",
    ),
    RunStepDefinition(
        key="record-market-orders",
        label="記錄市場資料",
        description="把本輪讀到的市場利率快照寫入 SQLite。",
    ),
    RunStepDefinition(
        key="load-strategy-inputs",
        label="載入策略參考資料",
        description="載入策略設定、FRR、BTC 價格與市場分析建議。",
    ),
    RunStepDefinition(
        key="calculate-decisions",
        label="計算策略決策",
        description="決定每個幣是否下單、下幾筆、金額與利率。",
    ),
    RunStepDefinition(
        key="record-decisions",
        label="保存策略決策",
        description="保存本輪每個幣的策略決策快照，供 Dashboard 回看。",
    ),
    RunStepDefinition(
        key="prepare-offers",
        label="準備委託",
        description="依策略決策整理本輪要建立的 lending offers。",
    ),
    RunStepDefinition(
        key="record-dry-run-offers",
        label="記錄模擬委託",
        description="模擬模式只寫本地紀錄，不送出到交易所。",
    ),
    RunStepDefinition(
        key="validate-live-offers",
        label="Live 金額安全檢查",
        description="Live 模式下單前檢查單筆與本輪總額上限。",
    ),
    RunStepDefinition(
        key="record-live-intents",
        label="建立 Live 委託意圖",
        description="真正送單前先寫入本地 intent，方便追蹤嘗試紀錄。",
    ),
    RunStepDefinition(
        key="submit-live-offers",
        label="送出 Bitfinex 委託",
        description="Live 模式呼叫交易所建立 lending offer。",
    ),
    RunStepDefinition(
        key="update-offer-results",
        label="更新委託結果",
        description="成功標記 created，失敗標記 failed 並保存錯誤訊息。",
    ),
    RunStepDefinition(
        key="finish-run",
        label="完成本次執行",
        description="寫入本輪 completed/failed 與摘要訊息。",
    ),
    RunStepDefinition(
        key="send-notifications",
        label="發送通知",
        description="發送摘要、錯誤或長天期委託通知。",
    ),
)

RUN_STEPS_BY_KEY = {step.key: step for step in RUN_STEP_DEFINITIONS}


def run_step_label(step_key: str) -> str:
    return RUN_STEPS_BY_KEY[step_key].label
