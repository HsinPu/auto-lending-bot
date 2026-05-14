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
        key="read-previous-active-loans",
        label="讀取本地舊放貸資料",
        description="讀取上一輪保存在 SQLite 的 active loans，用來比對新成交。",
    ),
    RunStepDefinition(
        key="read-active-loans",
        label="讀取交易所放貸中資料",
        description="從交易所讀取目前已成交、正在放貸中的資料。",
    ),
    RunStepDefinition(
        key="replace-active-loans",
        label="更新本地放貸中資料",
        description="用交易所最新 active loans 取代本地快照。",
    ),
    RunStepDefinition(
        key="detect-new-active-loans",
        label="檢查新成交放貸",
        description="比對上一輪與這一輪的放貸中資料，必要時發送成交通知。",
    ),
    RunStepDefinition(
        key="read-lending-balances",
        label="讀取 Lending 可用餘額",
        description="讀取 Funding/Lending wallet 裡可拿來放貸的幣種與金額。",
    ),
    RunStepDefinition(
        key="check-open-offer-rebalance-setting",
        label="檢查未成交委託同步設定",
        description="檢查是否啟用 open offer rebalance。",
    ),
    RunStepDefinition(
        key="sync-open-offers",
        label="檢查未成交委託",
        description="視設定同步目前還掛在市場上的未成交委託。",
    ),
    RunStepDefinition(
        key="replace-open-offers",
        label="更新本地未成交委託",
        description="用交易所最新 open offers 更新本地快照。",
    ),
    RunStepDefinition(
        key="check-open-offer-cancel-setting",
        label="檢查舊委託取消設定",
        description="檢查目前是否允許取消舊委託。",
    ),
    RunStepDefinition(
        key="rebalance-open-offers",
        label="處理舊委託",
        description="視設定決定是否保留或取消不符合策略的舊委託。",
    ),
    RunStepDefinition(
        key="evaluate-open-offer-cancel",
        label="評估舊委託是否取消",
        description="逐筆判斷舊委託是否應該保留或取消。",
    ),
    RunStepDefinition(
        key="cancel-open-offer",
        label="取消舊委託",
        description="取消一筆不符合策略且允許取消的舊委託。",
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
        key="load-strategy-config",
        label="載入策略設定",
        description="載入該幣的策略設定與覆寫值。",
    ),
    RunStepDefinition(
        key="load-frr-rate",
        label="讀取 FRR 利率",
        description="需要 FRR 作為最低利率時，讀取該幣 FRR。",
    ),
    RunStepDefinition(
        key="load-btc-price",
        label="讀取 BTC 參考價格",
        description="需要 BTC depth 換算時，讀取該幣 BTC 價格。",
    ),
    RunStepDefinition(
        key="load-market-analysis-rate",
        label="讀取市場分析建議利率",
        description="從 SQLite 讀取市場分析建議最低日利率。",
    ),
    RunStepDefinition(
        key="calculate-active-amount",
        label="計算已放貸金額",
        description="計算該幣目前已成交、正在放貸中的金額。",
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
        key="record-dry-run-offer",
        label="記錄模擬委託",
        description="模擬模式逐筆寫本地委託紀錄，不送出到交易所。",
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
