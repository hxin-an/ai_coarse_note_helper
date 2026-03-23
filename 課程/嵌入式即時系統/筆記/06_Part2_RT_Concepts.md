# 嵌入式即時系統 — uCOS Part 2 Real-Time System Concepts

> 來源：`uCOS Part 2 real-time system concept(fixed).pdf` | 產生日期：2026-03-24

## 前言

---

本份筆記整理 uC/OS-II Part 2 的即時系統理論基礎，涵蓋多工模型、任務組成要素、五種任務狀態及轉換 API、情境切換成本、核心職責與 overhead、排程器分類（可搶占 / 不可搶占、優先權驅動 / 截止期驅動）、中斷處理完整流程與三項計時指標、時鐘節拍機制，以及記憶體需求估算。這些概念是理解 uC/OS-II 核心實作（Part 3）的必要前提，也直接對應 IC 設計面試中常見的即時系統設計問題。

## 大綱

---

- 多工（Multitasking）
- 任務（Task）
  - 任務的四大組成要素
  - 任務、堆疊與 TCB 的記憶體配置
- 任務狀態機（Task States）
  - 五大狀態定義
  - 狀態轉換 API 對照
- 情境切換（Context Switch）
  - 切換成本
  - Context switch overhead 的計費對象
- 核心（Kernel）
  - 核心職責
  - 核心的 time / space overhead
  - uC/OS-II 服務執行時間參考
- 排程器（Scheduler）
  - 排程器定義與分類
  - 不可搶占核心（Non-Preemptive Kernel）
  - 可搶占核心（Preemptive Kernel）
- 中斷處理（Interrupt Handling）
  - 中斷的種類
  - 非搶占核心的 ISR 流程（七步驟）
  - 可搶占核心的 ISR 流程（七步驟）
  - 中斷延遲公式
  - 中斷計時三指標（Latency / Response / Recovery）
  - ISR 執行時間最佳實踐
  - 巢狀中斷（Nested Interrupts）
- 時鐘節拍（Clock Tick）
- `OSTimeDly()` 的時間不精確性
- 記憶體需求估算
  - 總 RAM 公式
  - 堆疊溢位的危險來源

---

## 多工（Multitasking）

---

**多工（Multitasking）**是指排程器在數個任務之間快速切換 CPU，使多個任務看似同時執行。

- **邏輯上並行**：各任務在邏輯上同時執行，但在單核心系統中同一瞬間只有一個任務佔用 CPU。
- **排程器決策**：排程器（scheduler）決定每個任務獲得多少 CPU 時間，以及切換的時機。

---

## 任務（Task）

---

在作業系統觀點下，**任務（task）**、執行緒（thread）、行程（process）三個詞在 uC/OS-II 的脈絡中可互換使用。

### 任務的四大組成要素

- **優先權（Priority）**：0 到 63 共 64 個等級，數字越小優先權越高；62 保留給統計任務（Stat Task），63 保留給閒置任務（Idle Task）。
- **暫存器集合（Set of Registers）**：任務的 CPU 情境（context），在情境切換時儲存至堆疊並在恢復時還原。
- **獨立堆疊（Own Stack）**：每個任務擁有獨立堆疊空間，用於儲存局部變數、函式呼叫返回位址與情境資料；大小需根據最深呼叫路徑手動估算。
- **管理資訊（Housekeeping Information / TCB）**：核心為每個任務維護的 **任務控制區塊（TCB, Task Control Block）**，記錄優先權、狀態、堆疊指標等所有執行資訊。

### 任務、堆疊與 TCB 的記憶體配置

各任務的堆疊（Stack）與 TCB 均存放於記憶體（MEMORY）中；CPU 內部僅有一份真實的暫存器集合，情境切換時核心將 TCB 內的堆疊指標（SP）載入 CPU，即可還原該任務的情境。

---

## 任務狀態機（Task States）

---

即時週期任務的結構為一個大型**無限迴圈（big, infinite loop）**，不會主動 return。uC/OS-II 定義五種任務狀態，核心透過特定 API 驅動狀態轉換。

### 五大狀態定義

| 狀態 | 說明 |
|------|------|
| **Dormant（休眠）** | 任務程式碼存在於記憶體，但尚未向核心註冊，不參與排程 |
| **Ready（就緒）** | 已向核心註冊，等待 CPU，位於就緒列表中 |
| **Running（執行中）** | 目前佔用 CPU；單核心系統中同一時間只有一個任務處於此狀態 |
| **Waiting（等待中）** | 等待某事件（計時到期、旗號、訊息等），不佔用 CPU |
| **ISR Running（中斷執行中）** | CPU 正在執行中斷服務常式，被中斷的任務暫時停止 |

### 狀態轉換 API 對照

- **Dormant 進入 Ready**：呼叫 `OSTaskCreate()` 或 `OSTaskCreateExt()`，向核心註冊任務。
- **Ready 進入 Running**：排程器選出最高優先權就緒任務（HPT）後執行情境切換。
- **Running 進入 Waiting**：呼叫 `OSTimeDly()`、`OSSemPend()`、`OSMboxPend()`、`OSQPend()`、`OSTaskSuspend()` 等 pending / suspend 類 API。
- **Waiting 進入 Ready**：條件滿足（計時到期、旗號釋放、訊息抵達、`OSTimeDlyResume()`），核心將任務移回就緒列表；`OSTimeTick()` 也會觸發此轉換。
- **Running 進入 Dormant**：呼叫 `OSTaskDel()`，將任務從核心移除。
- **Running 進入 ISR Running**：發生硬體中斷，CPU 跳至 ISR；原任務被暫停。
- **ISR Running 結束後**：ISR 呼叫 `OSIntExit()`，核心重新評估排程（可搶占核心可能切換至 HPT；不可搶占核心回到原任務）。

---

## 情境切換（Context Switch）

---

**情境切換（Context Switch）**發生在排程器將 CPU 從當前任務切換到另一個任務時：核心儲存當前任務的情境（所有 CPU 暫存器），再還原目標任務的情境。

### 切換成本

- **額外時間 overhead**：情境切換本身消耗 CPU 週期，屬於系統 overhead，不執行應用邏輯。
- **現代 CPU 的惡化因素**：現代處理器具備深層管線（pipeline）與大型暫存器檔（large register files）；情境切換後管線需重新填充，實際代價遠超暫存器存取本身。因此，**密集的情境切換（intensive context switches）應盡量避免**。

### Context Switch Overhead 的計費對象

情境切換的時間 overhead 計入兩類任務：

- **搶占任務（Preempting tasks）**：觸發搶占的高優先權任務，其執行時間中包含被計入的切換成本。
- **被阻塞的任務（Blocked tasks）**：因等待事件而被移出 Running 狀態的任務，其等待時間中也包含切換 overhead。

此 overhead 是 RTOS 規格的一部分，必須在系統設計時納入最壞執行時間（WCET）分析。

---

## 核心（Kernel）

---

**核心（Kernel）**是 RTOS 中負責管理任務與協調任務間通訊的核心軟體層。

### 核心職責

- **任務管理（Task Management）**：建立、刪除、暫停、恢復任務，以及執行情境切換。
- **任務間通訊（Inter-task Communication）**：提供旗號（semaphore）、訊息佇列（message queue）、信箱（mailbox）等同步與通訊機制。

### 核心的 Time / Space Overhead

核心引入兩類額外代價：

- **時間 overhead（Time Overhead）**：每次呼叫核心服務（旗號操作、訊息傳遞、計時控制等）均需消耗額外 CPU 週期。這些時間必須計入系統的即時性分析。
- **空間 overhead（Space Overhead）**：核心常駐於 RAM 和/或 ROM 中，佔用靜態記憶體；各任務的 TCB、就緒列表、事件控制區塊（ECB）等資料結構也需要 RAM 空間。

### uC/OS-II 服務執行時間參考

以 33 MHz 80186 處理器為參考，各類 uC/OS-II 服務的執行時間（單位：微秒）如下（摘自教材 Table 9.3）：

| 服務類別 | 代表 API | 典型執行時間（µs） |
|------|------|------|
| **Miscellaneous** | `OSInit()`, `OSStart()`, `OSSchedLock/Unlock()` | 0–87 |
| **Interrupt Management** | `OSIntEnter()`, `OSIntExit()` | 4–948 |
| **Message Mailboxes** | `OSMboxAccept/Create/Pend/Post/Query()` | 15–305 |
| **Memory Partition Mgmt** | `OSMemCreate/Get/Put/Query()` | 21–400 |
| **Message Queues** | `OSQAccept/Create/Flush/Pend/Post/Query()` | 14–495 |
| **Semaphore Management** | `OSSemAccept/Create/Pend/Post/Query()` | 10–931 |

此表的意義在於：設計時必須將這些服務呼叫的執行時間計入中斷延遲與任務 WCET 分析，而非假設核心呼叫為零成本。

---

## 排程器（Scheduler）

---

**排程器（Scheduler）**是核心的一部分，負責從就緒列表中選出下一個要執行的任務。

### 排程器定義與分類

- **可搶占 vs. 不可搶占（Preemptive vs. Non-preemptive）**：決定 ISR 結束後 CPU 控制權是否立即交給最高優先權就緒任務，還是回到被中斷的原任務。
- **優先權驅動 vs. 截止期驅動（Priority-driven vs. Deadline-driven）**：決定選擇任務的依據是靜態優先權數字，還是任務的截止期（deadline）。
- **uC/OS-II 的選擇**：採用**可搶占、優先權驅動**排程；在任何時刻，就緒列表中優先權最高的任務（HPT, Highest Priority Task）都會立即獲得 CPU 控制權。

### 不可搶占核心（Non-Preemptive Kernel）

#### 運作機制

- **情境切換觸發條件**：只有在任務**主動放棄 CPU**（呼叫 blocking API，如 `OSSemPend()`、`OSTimeDly()`）時，才發生情境切換。任務必須頻繁主動讓出，才能維持系統回應性。
- **ISR 結束後的行為**：ISR 結束後，CPU **永遠回到被中斷的原任務**，即使 ISR 已將更高優先權的任務設為就緒。高優先權任務必須等到低優先權任務主動讓出後才能執行。

#### Race Condition 分析

- **Task-Task Race**：**不存在**（因為任務不會在另一個任務執行中途搶占 CPU，無需臨界區保護）。
- **Task-ISR Race**：**仍然存在**（ISR 可在任何時刻搶占正在執行的任務）。解決方法：關閉中斷（interrupt disabling）或使用延遲任務（deferred tasks）。

#### 優缺點

| | 說明 |
|--|------|
| **優點（Pros）** | 設計簡單（simple）、行為可預期、強健（robust） |
| **缺點（Cons）** | 回應性差（low response）、可排程性差（poor schedulability）；高優先權任務無法即時回應事件 |

#### 非搶占核心的七步驟 ISR 流程

1. **任務執行中被中斷**：低優先權任務正在執行。
2. **中斷向量跳轉**：若中斷已啟用，CPU 跳至 ISR。
3. **ISR 處理事件**：ISR 處理事件，並將高優先權任務設為就緒（Ready）。
4. **ISR 返回原任務**：ISR 執行 RETI，CPU 回到被中斷的低優先權任務繼續執行。
5. **低優先權任務繼續執行**：從被中斷的指令之後繼續執行。
6. **低優先權任務主動讓出 CPU**：呼叫核心服務主動放棄 CPU。
7. **高優先權任務執行**：排程器選出高優先權任務，開始處理 ISR 所觸發的事件。

### 可搶占核心（Preemptive Kernel）

#### 運作機制

- **即時搶占**：就緒列表中只要有任務的優先權高於當前任務，就立即發生情境切換；uC/OS-II（以及多數 RTOS）均採用此設計。
- **ISR 結束後的行為**：ISR 結束後，排程器評估就緒列表；若有更高優先權的就緒任務，**ISR 不回到被中斷的原任務**，而是直接切換至高優先權任務執行。

#### Race Condition 分析

- **Task-Task Race**：**存在**（高優先權任務可在任何時刻搶占低優先權任務，共享資料需臨界區保護）。
- **Task-ISR Race**：**存在**（ISR 可在任務執行中途搶占，共享資料需保護）。

因此，可搶占核心同時存在 task-task 與 task-ISR 兩種競爭條件，需要更嚴格的同步機制。

#### 可搶占核心的七步驟 ISR 流程

1. **任務執行中被中斷**：低優先權任務正在執行。
2. **中斷向量跳轉**：若中斷已啟用，CPU 跳至 ISR。
3. **ISR 處理事件，核心服務被呼叫**：ISR 處理事件，並透過核心服務（如 `OSSemPost()`）將高優先權任務設為就緒。
4. **（核心評估排程）**：核心發現有更高優先權任務就緒，準備情境切換（此步驟在 `OSIntExit()` 內部執行）。
5. **情境切換至高優先權任務**：核心執行情境切換，高優先權任務開始執行，處理 ISR 所觸發的事件。高優先權任務完成後呼叫 blocking API 進入等待狀態。
6. **（情境切換回低優先權任務）**：核心再次評估排程，選出低優先權任務。
7. **低優先權任務恢復執行**：從被中斷的指令之後繼續執行。

---

## 中斷處理（Interrupt Handling）

---

### 中斷的種類

- **硬體中斷（Hardware Interrupt）**：由外部裝置或硬體事件觸發，包含時鐘節拍（clock tick）、I/O 事件、硬體錯誤等。
- **軟體觸發中斷（Software-Trigger Interrupt）**：由軟體指令主動觸發，例如 uC/OS-II 的情境切換（context switch 使用軟體中斷指令）、除以零（divide-by-zero）等。

中斷的基本流程：儲存 CPU 情境至堆疊，查詢中斷向量表（IVT），跳至 ISR；ISR 完成後根據核心類型返回被中斷的任務或 HPT。

### 非搶占核心的 ISR 流程（七步驟）

詳見「排程器 → 不可搶占核心 → 七步驟 ISR 流程」。

### 可搶占核心的 ISR 流程（七步驟）

詳見「排程器 → 可搶占核心 → 七步驟 ISR 流程」。

### 中斷延遲公式

**中斷延遲（Interrupt Latency）**定義為從硬體觸發中斷到 ISR 執行第一條指令的時間。關閉中斷的持續時間越長，中斷延遲越高：

$$T_{latency} = T_{\text{interrupt-disable-max}} + T_{\text{time to start executing the first ISR instruction}}$$

- **關鍵影響因素**：核心在臨界區（`OS_ENTER_CRITICAL` 到 `OS_EXIT_CRITICAL`）關閉中斷的最長持續時間，直接決定延遲下限；此段越短，即時性越好。

### 中斷計時三指標（Latency / Response / Recovery）

| 指標 | 定義 |
|------|------|
| **Interrupt Latency（中斷延遲）** | 中斷觸發到 ISR 開始執行第一條指令的時間 |
| **Interrupt Response（中斷回應）** | 中斷觸發到系統開始實際處理事件的總時間（含 Kernel ISR Entry function） |
| **Interrupt Recovery（中斷恢復）** | ISR 結束後，系統恢復排程並切換至最高優先權就緒任務所需的時間 |

在可搶占核心中，Recovery 包含兩條路徑（如教材圖示）：

- **路徑 A**：ISR 未喚醒更高優先權任務，CPU Context Saved 後直接 restore，回到原任務（成本較低）。
- **路徑 B**：ISR 喚醒更高優先權任務，觸發 Kernel ISR Exit function 執行情境切換後才恢復執行（成本較高，但確保即時性）。

### ISR 執行時間最佳實踐

在大多數情況下，ISR 應完成以下最小工作並盡快返回：

- **儲存情境（Save Context）**：保存當前任務的 CPU 暫存器。
- **識別中斷（Recognize Interrupt）**：確認中斷來源與原因。
- **取得資料或狀態（Obtain Data/Status）**：從中斷裝置讀取必要資料。
- **恢復任務執行（Resume Task Execution）**：返回任務或觸發情境切換。

**ISR 應盡可能短**，原因有二：

- **增加任意任務的延遲**：ISR 執行時間會疊加到被中斷的任何任務上，影響系統整體的即時性。
- **禁止在 ISR 中執行大型工作**：需要長時間處理的工作應交給**工作任務（worker task）**，由 ISR 透過旗號或訊息喚醒該任務執行後續處理。

### 巢狀中斷（Nested Interrupts）

**巢狀中斷（Nested Interrupts）**允許高優先權中斷在低優先權 ISR 執行期間搶占 CPU，形成多層 ISR 巢狀（如 ISR#1 被 ISR#2 搶占，ISR#2 再被 ISR#3 搶占）。

- **計數追蹤**：uC/OS-II 以 `OSIntNesting` 計數器追蹤巢狀深度；`OSIntExit()` 僅在計數歸零時才執行排程評估。
- **堆疊需求**：每層巢狀中斷均需儲存情境，記憶體規劃時需乘以最大巢狀層數（見記憶體需求估算）。

---

## 時鐘節拍（Clock Tick）

---

**時鐘節拍（Clock Tick）**是 uC/OS-II 的系統心跳，由硬體定時器以固定頻率產生週期性中斷。

- **本質**：屬於週期性硬體中斷（periodic hardware interrupt）。
- **功能**：每次中斷觸發 `OSTimeTick()`，掃描所有 TCB 並更新延遲計數器；計數到期的任務被移回就緒列表。
- **Tick Rate 的取捨**：Tick rate 越高，系統回應性（responsiveness）越好，但情境切換頻率（context switch frequency）也越高，CPU overhead 隨之增加；需根據應用需求平衡。
- **啟動順序**：時鐘節拍硬體中斷必須在 `OSStart()` 之後才能開啟；若在核心初始化完成前觸發，會存取尚未建立的資料結構，導致未定義行為。

---

## `OSTimeDly()` 的時間不精確性

---

`OSTimeDly(n)` 讓任務延遲 $n$ 個時鐘節拍，但實際「睡眠時間」可能永遠無法如規格所述般精確（the actual "sleep time" may never be as accurate as specified）。

誤差的三個來源：

- **高優先權任務搶占（HPT 等待）**：延遲到期後，若就緒列表中有更高優先權任務，本任務必須等待 HPT 主動讓出 CPU 才能繼續執行。
- **ISR 執行時間（ISR Overhead）**：時鐘節拍 ISR 本身消耗時間，這段時間不計入節拍週期，導致實際等待時間略長。
- **節拍的離散性（Tick Count is Discrete）**：呼叫 `OSTimeDly()` 的時機可能落在節拍週期中間；若在下一個節拍即將到來前才呼叫，第一個節拍幾乎立即到期。教材圖示顯示：即使呼叫「delay 1 tick」，實際延遲可能只有 19 ms、17 ms 或 27 ms（tick 週期 20 ms）。

$$( n-1 ) \cdot T_{tick} \leq T_{actual} \leq ( n+1 ) \cdot T_{tick}$$

若對時間精度有嚴格要求，應使用硬體計時器直接觸發事件，而非依賴 `OSTimeDly()`。

---

## 記憶體需求估算

---

### 總 RAM 公式

RAM 使用量由三部分構成：

$$\text{RAM}_{total} = \text{RAM}_{code} + \text{RAM}_{data+stack} + \sum_{i=1}^{N}(\text{Stack}_{task_i} + \text{Stack}_{ISR\text{-}nesting\text{-}max})$$

| 項目 | 說明 | 確定時機 |
|------|------|------|
| **Code（程式碼）** | 可執行二進位的大小 | 編譯期可確定 |
| **Data + Stack（全域變數含 free list）** | 全域變數與靜態資料 | 編譯期可確定 |
| **Task Stacks（各任務堆疊）** | 所有任務獨立堆疊的總和 | 離線分析，非確定性 |
| **ISR Nesting Stack** | 支援巢狀中斷的最大堆疊需求，每個 task 均需計入 | 離線分析 |

教材公式（紅字強調）：**Total RAM = application requirement + kernel requirement + SUM( each task(stack + MAX(ISR nesting)) )**

### 堆疊溢位的危險來源

以下情況容易導致堆疊使用量超過估算值，需特別注意：

- **大型陣列或結構作為局部變數（Large Arrays/Structures as Local Variables）**：局部變數分配在堆疊上，大型資料結構會快速耗盡堆疊空間。
- **遞迴函式呼叫（Recursive Function Calls）**：每層遞迴都會推入一個新的 stack frame，深度遞迴可能導致堆疊溢位。
- **ISR 巢狀（ISR Nesting）**：每層 ISR 均需在當前任務的堆疊上儲存情境，巢狀越深消耗越多。
- **帶大量引數的函式呼叫（Function Calls with Many Arguments）**：引數與返回位址均存放於堆疊，參數過多會增加每次呼叫的堆疊佔用。

實務建議：初期預留 50% 以上裕量，再透過 `OSTaskStkChk()` 在執行時期監控實際使用量並收斂。

---

**備註：本筆記整理 uC/OS-II Part 2 的即時系統理論基礎，核心貢獻在於以五狀態任務模型、核心 overhead 分析、非搶占/可搶占排程器的 race condition 對比、中斷計時三指標（Latency/Response/Recovery）與記憶體需求公式，為後續 Part 3 的核心資料結構與排程實作建立完整的概念框架。**
