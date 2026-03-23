# 嵌入式即時系統 — uCOS Part 3 Kernel Structure

> 來源：`uCOS Part 3 kernel structure.pdf` | 產生日期：2026-03-24

## 前言

---

本份筆記整理 uC/OS-II Part 3 的核心結構實作，涵蓋臨界區的保護機制（為何關閉中斷優於旗號）、任務結構與生命週期、TCB 的完整欄位解析、O(1) 點陣圖就緒列表的設計與操作、`OS_Sched()` 排程器原始碼、任務層級與 ISR 層級情境切換的差異、十步驟 ISR 模板、`OSTimeTick()` 的 O(n) 掃描與 Delta List 替代方案、排程器鎖定機制，以及 `OSInit()` → `OSStart()` 啟動序列。這些內容是 uC/OS-II 移植與系統設計面試的核心考點。

## 大綱

---

- 臨界區（Critical Sections）
  - 臨界區定義
  - 為何不用旗號保護核心臨界區
  - 為何 ISR 不可呼叫 Blocking API
  - 關閉中斷作為核心臨界區保護機制
  - `OS_CRITICAL_METHOD=2`：PSW Push/Pop 實作
  - 為何不用 Method 1（直接啟用/關閉）
  - 使用規則與注意事項
- 任務結構（Task Structure）
  - 任務的定義與形式
  - 優先權管理（64 個等級）
  - 任務生命週期 API
  - 任務狀態詳解（五狀態 + 轉換條件）
- 任務控制區塊（TCB）
  - TCB 結構全覽
  - 各欄位功能說明
  - TCB 自由列表與 `OS_TCBInit()`
- 就緒列表與排程（Ready List and Scheduling）
  - 就緒列表設計（O(1) 點陣圖）
  - `OSRdyGrp` + `OSRdyTbl[8]` 結構
  - `OSMapTbl`：新增 / 移除任務操作
  - `OSUnMapTbl`：O(1) 查找最高優先權
  - `OS_Sched()` 原始碼解析
  - 任務層級情境切換（Task-Level Context Switch）
- 中斷處理（Interrupt Handling）
  - 十步驟 ISR 模板
  - `OSIntEnter()` / `OSIntExit()` 原始碼
  - ISR 層級 vs. 任務層級情境切換
- 時鐘節拍（Clock Tick）
  - `OSTimeTick()` 原始碼
  - O(n) 線性掃描 vs. Delta List
- 排程器鎖定（Scheduler Lock）
  - `OSSchedLock()` / `OSSchedUnlock()` 原始碼
  - 三種競爭條件防護機制對比
  - 中斷處理 Do's and Don'ts
- 閒置任務（Idle Task）
- 啟動序列（Startup Sequence）

---

## 臨界區（Critical Sections）

---

**臨界區（Critical Section）**是一段不安全於競爭條件（race condition）的程式碼，又稱為不可重入程式碼（non-reentrant code）。

### 臨界區定義

- **核心內部的 task-task race**：核心程式碼中的臨界區通常很短；使用旗號或 mutex 保護過於耗費資源（too heavy-duty），且在臨界區內不宜發生情境切換。
- **task-ISR race**：ISR 與任務共享資料時形成 task-ISR race，旗號無法解決，因為 ISR 不可呼叫 blocking API。

### 為何 ISR 不可呼叫 Blocking API

ISR 中呼叫 `OSSemPend()` 等 blocking API 會導致兩個問題：

- **潛在死鎖（Potential Deadlock）**：被中斷的任務本身可能正是負責處理當前中斷的一部分；若 ISR 等待該任務持有的旗號，系統即死鎖。
- **非預期的長延遲（Unexpected Long Delay）**：讓被中斷任務的等待時間無法預測，破壞即時性保證。

### 關閉中斷作為核心臨界區保護機制

關閉中斷是 uC/OS-II 保護核心臨界區的核心機制，適用原因有二：

- **適用於核心程式碼**：核心臨界區通常很短，關閉中斷的代價可接受。
- **解決 task-ISR race**：ISR 無法在中斷關閉期間搶占，可安全保護共享資料。

注意：此方法在多處理器系統中無效，多處理器需改用 **spinlock**。

```c
{
    OS_ENTER_CRITICAL();  /* 關閉中斷，進入臨界區 */
    /* Critical Section */
    OS_EXIT_CRITICAL();   /* 還原中斷狀態，離開臨界區 */
}
```

### `OS_CRITICAL_METHOD=2`：PSW Push/Pop 實作

uC/OS-II 的 x86 移植使用 **Method 2**：將處理器狀態字（PSW, Processor Status Word）推入 / 彈出堆疊，精確記錄巢狀呼叫時的中斷狀態。

```c
/* x86 port — OS_CRITICAL_METHOD == 2 */
#define OS_ENTER_CRITICAL()  asm("PUSHF")  /* 將 PSW（含 IF 旗標）壓入堆疊 */
#define OS_EXIT_CRITICAL()   asm("POPF")   /* 從堆疊還原 PSW */
```

- **運作原理**：`PUSHF` 將目前 PSW 壓入堆疊（含中斷啟用旗標 IF）；`POPF` 從堆疊還原 PSW，自動恢復呼叫前的中斷狀態，而非無條件啟用。
- **巢狀呼叫安全**：每次 `PUSHF/POPF` 使用獨立的堆疊 frame，巢狀的 `OS_ENTER_CRITICAL` / `OS_EXIT_CRITICAL` 可精確還原各層中斷狀態。

### 為何不用 Method 1（直接啟用/關閉）

**Method 1** 使用無條件的 `disable_interrupt()` / `enable_interrupt()` 指令，存在根本缺陷：

- **巢狀呼叫破壞**：若核心服務 A 在已關閉中斷的狀態下呼叫核心服務 B，服務 B 的 `OS_EXIT_CRITICAL()` 會立即重新啟用中斷，而非等到服務 A 的 `OS_EXIT_CRITICAL()` 才啟用。這使中斷在服務 A 的臨界區尚未結束時被重新開啟，導致競爭條件。

### 使用規則與注意事項

- **中斷關閉時間越短越好**：中斷關閉的最長持續時間直接決定中斷延遲（interrupt latency）的下界，影響整個 RTOS 的即時性規格。
- **禁止在中斷關閉期間呼叫系統服務**：例如中斷關閉時呼叫 `OSTimeDly()`，時鐘節拍中斷被阻擋，導致系統掛起（hang）。
- **基本規則**：不可在中斷關閉狀態下（或在 ISR 中）呼叫任何系統服務。

---

## 任務結構（Task Structure）

---

**任務（Task）**是主動執行計算的實體。在即時系統中，週期性任務的標準結構為一個大型無限迴圈。

### 任務的定義與形式

```c
void YourTask (void *pdata)
{
    for (;;) {
        /* USER CODE */
        /* 必須呼叫其中一種讓出 CPU 的 API，否則低優先權任務永遠無法執行 */
        OSMboxPend(...);          /* 等待信箱訊息 */
        OSSemPend(...);           /* 等待旗號 */
        OSTimeDly(...);           /* 計時延遲 */
        OSTaskDel(OS_PRIO_SELF);  /* 刪除自身（非週期性任務用） */
        /* USER CODE */
    }
}
```

- **無限迴圈**：週期性任務不可自行 return，必須永遠循環執行。
- **blocking call 必要性**：每次迴圈必須呼叫至少一個 blocking API，讓排程器得以切換至其他任務。

### 優先權管理（64 個等級）

- **優先權範圍**：0 到 63，共 64 個等級；數字越小優先權越高，每個任務擁有唯一優先權。
- **保留等級**：62 保留給統計任務（Stat Task），63 保留給閒置任務（Idle Task），應用任務可使用 0–61。
- **可排程性考量**：唯一優先權在嵌入式系統中通常可行，因任務數量有限；但若可用優先權不足，會損害即時排程器的可排程性（schedulability）。

### 任務生命週期 API

- **建立任務**：`OSTaskCreate(task, pdata, ptos, prio)` 或 `OSTaskCreateExt(...)` 初始化 TCB、堆疊、優先權表與就緒列表。
- **變更優先權**：`OSTaskChangePrio(oldPrio, newPrio)` 在執行期間動態調整任務優先權。
- **刪除任務**：任務可呼叫 `OSTaskDel(OS_PRIO_SELF)` 刪除自身；非週期性任務在工作完成後即可刪除。

### 任務狀態詳解（五狀態 + 轉換條件）

| 狀態 | 說明 | 進入條件 |
|------|------|------|
| **Dormant（休眠）** | 程式碼存在於記憶體但未建立為任務 | 初始狀態；`OSTaskDel()` 後回到此狀態 |
| **Ready（就緒）** | 已建立，等待 CPU | `OSTaskCreate()` 後；事件發生或 `OSTimeTick()` 到期後 |
| **Running（執行中）** | 正佔用 CPU | 排程器從 Ready 中選出此任務 |
| **Waiting（等待中）** | 等待計時、旗號、訊息或旗標 | 呼叫 `OSTimeDly()`、`OSSemPend()`、`OSMboxPend()`、`OSQPend()`、`OSFlagPend()`、`OSTaskSuspend()` |
| **ISR Running** | CPU 正執行 ISR，任務堆疊被 ISR 使用 | 硬體中斷觸發 |

額外轉換規則：

- **Running 任務永遠被 ISR 搶占**，除非中斷已被關閉。
- **ISR 返回時**，排程器重新評估是否需要情境切換（呼叫 `OSIntExit()`）。
- **任何時刻若所有任務都不在 Ready 狀態**，閒置任務（priority 63）執行。

---

## 任務控制區塊（TCB）

---

**TCB（Task Control Block）**是核心為每個任務維護的資料結構，記錄任務的所有執行狀態。CPU 暫存器儲存在任務的堆疊中，而非 TCB 本身。

### TCB 結構全覽

```c
typedef struct os_tcb {
    OS_STK        *OSTCBStkPtr;     /* 當前堆疊頂端指標（TOS） */

    /* 以下欄位需 OS_TASK_CREATE_EXT_EN == 1 */
    void          *OSTCBExtPtr;     /* 使用者定義的 TCB 擴展指標 */
    OS_STK        *OSTCBStkBottom;  /* 堆疊底端指標（BOS） */
    INT32U         OSTCBStkSize;    /* 堆疊大小（元素數，非位元組） */
    INT16U         OSTCBOpt;        /* OSTaskCreateExt() 的選項旗標 */
    INT16U         OSTCBId;         /* 任務識別碼（未來擴展用） */

    struct os_tcb *OSTCBNext;       /* 雙向鏈結：下一個 TCB */
    struct os_tcb *OSTCBPrev;       /* 雙向鏈結：上一個 TCB */

    OS_EVENT      *OSTCBEventPtr;   /* 正在等待的事件控制區塊指標 */
    void          *OSTCBMsg;        /* 從信箱或佇列接收的訊息指標 */

    INT16U         OSTCBDly;        /* 延遲計數 / 等待逾時計數 */
    INT8U          OSTCBStat;       /* 任務狀態（0 = Ready） */
    INT8U          OSTCBPrio;       /* 任務優先權 */

    INT8U          OSTCBX;          /* priority & 0x07（就緒列表欄位索引） */
    INT8U          OSTCBY;          /* priority >> 3（就緒列表列索引） */
    INT8U          OSTCBBitX;       /* OSMapTbl[priority & 0x07]（欄位遮罩） */
    INT8U          OSTCBBitY;       /* OSMapTbl[priority >> 3]（列遮罩） */

    BOOLEAN        OSTCBDelReq;     /* 刪除請求旗標（OS_TASK_DEL_EN） */
} OS_TCB;
```

### 各欄位功能說明

- **`OSTCBStkPtr`**：指向當前堆疊頂端（TOS）；宣告為結構第一個欄位，以便組合語言直接以 offset=0 存取，無需計算偏移量。
- **`OSTCBExtPtr`**：指向使用者自定義的 TCB 擴展資料（需 `OSTaskCreateExt()` 建立，設定 `OS_TASK_CREATE_EXT_EN=1`）。
- **`OSTCBStkBottom`**：指向堆疊底端（BOS）；搭配 `OSTCBStkSize` 用於堆疊使用量檢查（`OSTaskStkChk()`）。
- **`OSTCBStkSize`**：堆疊大小以元素數（element count）計算，非位元組；x86 下每個元素為 16 bits（`OS_STK` 型別），總位元組數 = `OSTCBStkSize × sizeof(OS_STK)`。
- **`OSTCBOpt`**：選項旗標，包含：
  - `OS_TASK_OPT_STK_CHK`：啟用堆疊使用量檢查
  - `OS_TASK_OPT_STK_CLR`：建立時清零堆疊
  - `OS_TASK_OPT_SAVE_FP`：浮點運算任務需在情境切換時額外儲存 FPU 暫存器
- **`OSTCBNext` / `OSTCBPrev`**：雙向鏈結，將所有使用中的 TCB 串接成 TCB 鏈結串列。
- **`OSTCBEventPtr`**：指向任務正在等待的事件控制區塊（ECB）。
- **`OSTCBDly`**：計時延遲計數器；`OSTimeDly()` 設定後，`OSTimeTick()` 每次遞減一，歸零時喚醒任務。也用於等待事件時的逾時計數。
- **`OSTCBStat`**：任務狀態旗標；0 表示就緒（Ready to run）。
- **`OSTCBX / OSTCBY / OSTCBBitX / OSTCBBitY`**：預先計算的就緒列表索引與遮罩，用於加速就緒列表操作（O(1)）：

```c
OSTCBY    = priority >> 3;               /* 列索引（0–7） */
OSTCBBitY = OSMapTbl[priority >> 3];     /* 列遮罩 */
OSTCBX    = priority & 0x07;             /* 欄索引（0–7） */
OSTCBBitX = OSMapTbl[priority & 0x07];   /* 欄遮罩 */
```

- **`OSTCBDelReq`**：布林值，表示是否有其他任務請求刪除此任務（`OSTaskDelReq()` 機制用）。

### TCB 自由列表與 `OS_TCBInit()`

- **靜態分配**：uC/OS-II 啟動時依 `OS_MAX_TASKS`（定義於 `OS_CFG.H`）建立 `OSTCBTbl[]` 陣列，將所有 TCB 以單向鏈結串接為 **TCB 自由列表（free list）**，頭指標為 `OSTCBFreeList`。
- **動態分配模擬**：任務建立時從 `OSTCBFreeList` 取出一個 TCB；任務刪除時將 TCB 歸還給 `OSTCBFreeList`。
- **`OS_TCBInit()`**：由 `OSTaskCreate()` 呼叫，初始化 TCB 各欄位、將 TCB 插入 TCB 鏈結串列，並將任務加入就緒列表。

---

## 就緒列表與排程（Ready List and Scheduling）

---

### 就緒列表設計（O(1) 點陣圖）

uC/OS-II 以點陣圖（bitmap）實作就緒列表，可在 O(1) 時間內找到最高優先權的就緒任務。

設計選項的複雜度對比：

| 資料結構 | 找最高優先權 | 說明 |
|------|------|------|
| **線性串列** | O(n) | 需掃描所有任務 |
| **最大堆積（Max Heap）** | O(log n) | 插入與刪除各 O(log n) |
| **點陣圖（Bitmap）** | O(1) | 使用查找表（lookup table）直接定位 |

### `OSRdyGrp` + `OSRdyTbl[8]` 結構

就緒列表由兩個全域變數組成：

- **`OSRdyGrp`**（8 bits）：每個 bit 對應一個群組（group），群組 i 中有任何任務就緒時，bit i 置 1。
- **`OSRdyTbl[8]`**（每個 8 bits）：`OSRdyTbl[y]` 記錄群組 y 中哪些優先權就緒；bit x 置 1 表示優先權 `(y×8 + x)` 的任務就緒。

映射關係：優先權 `prio` 的群組索引 `y = prio >> 3`，欄索引 `x = prio & 0x07`。

### `OSMapTbl`：新增 / 移除任務操作

```c
/* OSMapTbl 將索引（0–7）轉換為對應的單一 bit 遮罩 */
/* Index: 0    1    2    3    4    5    6    7   */
/* Mask:  0x01 0x02 0x04 0x08 0x10 0x20 0x40 0x80 */

/* 將任務加入就緒列表 */
OSRdyGrp             |= OSMapTbl[prio >> 3];      /* 設定 OSRdyGrp 的群組 bit */
OSRdyTbl[prio >> 3]  |= OSMapTbl[prio & 0x07];   /* 設定 OSRdyTbl 的任務 bit */

/* 將任務從就緒列表移除 */
if ((OSRdyTbl[prio >> 3] &= ~OSMapTbl[prio & 0x07]) == 0)
    OSRdyGrp &= ~OSMapTbl[prio >> 3]; /* 群組內無任何就緒任務時，清除群組 bit */
```

### `OSUnMapTbl`：O(1) 查找最高優先權

`OSUnMapTbl[256]` 是一張預先計算的查找表，輸入一個 8-bit 值，輸出其最低有效位（LSB）的位置（即最高優先權任務的索引）。

```c
/* 找出就緒列表中最高優先權的任務 */
y    = OSUnMapTbl[OSRdyGrp];          /* 找出有就緒任務的最高優先群組 */
x    = OSUnMapTbl[OSRdyTbl[y]];       /* 在群組內找出最高優先權任務 */
prio = (y << 3) + x;                  /* 計算實際優先權數值 */
```

範例：若 `OSRdyGrp = 0b00110010`，`OSUnMapTbl[0b00110010] = 1`（最低有效 1 的位置）。

### `OS_Sched()` 原始碼解析

```c
void OS_Sched (void)
{
    INT8U y;
    OS_ENTER_CRITICAL();
    /* (1) 若排程器已鎖定或正在處理中斷，不執行排程 */
    if ((OSLockNesting | OSIntNesting) == 0) {
        /* (2) 找出最高優先權就緒任務（HPT） */
        y = OSUnMapTbl[OSRdyGrp];
        OSPrioHighRdy = (INT8U)((y << 3) + OSUnMapTbl[OSRdyTbl[y]]);
        /* (3) 若 HPT 不是當前任務，執行情境切換 */
        if (OSPrioHighRdy != OSPrioCur) {
            OSTCBHighRdy = OSTCBPrioTbl[OSPrioHighRdy];
            OSCtxSwCtr++;           /* (4) 更新情境切換計數器 */
            OS_TASK_SW();           /* (5) 觸發軟體中斷 INT 80h */
        }
    }
    OS_EXIT_CRITICAL();
}
```

- **`(OSLockNesting | OSIntNesting) == 0`**：排程器鎖定（`OSSchedLock`）或正在處理中斷時，不執行排程，避免在不適當的時機切換任務。
- **`OS_TASK_SW()`**：展開為 `asm("int 0x80")`，產生軟體中斷 80h，進入情境切換 ISR。

### 任務層級情境切換（Task-Level Context Switch）

情境切換本質上發生在 ISR 返回時（clock tick ISR 或 context-switch ISR）。

- **任務主動讓出 CPU 時**（task-level context switch）：沒有真實硬體中斷，因此以 **`INT 80h` 軟體中斷**模擬，使情境切換可在 ISR 框架內統一處理。
- **切換步驟**：
  1. 將 LPT（低優先權任務）的所有暫存器與 PSW 儲存至其堆疊。
  2. 將 `OSTCBCur->OSTCBStkPtr` 更新為當前 SP，儲存堆疊頂端指標。
  3. 從 `OSTCBHighRdy->OSTCBStkPtr` 載入 HPT 的堆疊指標。
  4. 從 HPT 堆疊還原所有暫存器與 PSW，繼續執行 HPT。

---

## 中斷處理（Interrupt Handling）

---

### 十步驟 ISR 模板

uC/OS-II 的 ISR 以組合語言撰寫，標準模板如下：

```asm
YourISR:
    ; (1) 儲存所有 CPU 暫存器至被中斷任務的堆疊
    ;     （ISR 執行可能修改暫存器，必須先保存）
    Save all CPU registers;

    ; (2) 遞增中斷巢狀計數器 OSIntNesting
    Call OSIntEnter();

    ; (3) 若為第一層中斷（非巢狀），立即儲存當前 SP 至 TCB
    ;     （情境切換可能發生，需紀錄此時的 SP）
    if (OSIntNesting == 1)
        OSTCBCur->OSTCBStkPtr = SP;

    ; (4) 清除中斷裝置的中斷旗標
    Clear the interrupting device;

    ; (5) 重新啟用中斷（可選，允許更高優先權的巢狀中斷）
    Re-enable interrupts (optional);

    ; (6) 執行使用者 ISR 程式碼（處理事件、發布旗號/訊息等）
    Execute user ISR code to service the interrupt;

    ; (7) 呼叫 OSIntExit()，評估是否需要情境切換
    Call OSIntExit();

    ; (8) 若 OSIntExit() 執行了情境切換，返回此點時多個高優先任務可能已執行完畢
    ; (9) 還原所有 CPU 暫存器
    Restore all CPU registers;

    ; (10) 執行 IRET，返回被中斷的任務或 HPT
    Execute a return from interrupt (IRET);
```

- **步驟 (1) 和 (7)** 是 uC/OS-II 要求的額外步驟，用於支援可能發生的情境切換。
- **步驟 (3) 的關鍵**：只有在第一層中斷（`OSIntNesting == 1`）時才儲存 SP，因為巢狀中斷使用同一個任務堆疊，只需記錄第一層進入時的 SP 作為情境切換基準。

### `OSIntEnter()` / `OSIntExit()` 原始碼

```c
void OSIntEnter (void)
{
    OS_ENTER_CRITICAL();
    OSIntNesting++;         /* 遞增巢狀計數器 */
    OS_EXIT_CRITICAL();
}

void OSIntExit (void)
{
    OS_ENTER_CRITICAL();
    /* 僅在最外層 ISR 結束（OSIntNesting 歸零）且排程器未鎖定時執行排程 */
    if ((--OSIntNesting | OSLockNesting) == 0) {
        /* 找出 HPT */
        OSIntExitY    = OSUnMapTbl[OSRdyGrp];
        OSPrioHighRdy = (INT8U)((OSIntExitY << 3) +
                         OSUnMapTbl[OSRdyTbl[OSIntExitY]]);
        /* 若 HPT 不是當前任務，執行 ISR 層級情境切換 */
        if (OSPrioHighRdy != OSPrioCur) {
            OSTCBHighRdy = OSTCBPrioTbl[OSPrioHighRdy];
            OSCtxSwCtr++;
            OSIntCtxSw();   /* 注意：使用 OSIntCtxSw()，非 OS_TASK_SW() */
        }
    }
    OS_EXIT_CRITICAL();
}
```

### ISR 層級 vs. 任務層級情境切換

| 比較項目 | 任務層級（Task-Level） | ISR 層級（ISR-Level） |
|------|------|------|
| **觸發函式** | `OS_TASK_SW()` | `OSIntCtxSw()` |
| **觸發機制** | 軟體中斷 `INT 80h` | 直接在 `OSIntExit()` 內呼叫 |
| **原因** | 任務主動讓出 CPU，無硬體中斷 | ISR 結束時排程器發現更高優先權任務 |
| **本質** | 模擬 ISR 進行情境切換 | 真實 ISR 內直接切換 |

---

## 時鐘節拍（Clock Tick）

---

時鐘節拍 ISR 必須在 `OSStart()` 啟動排程後才能安裝，通常在啟動任務（startup task）中設定。時鐘節拍 ISR 遵循標準 ISR 模板，並在步驟 (6) 呼叫 `OSTimeTick()`。

### `OSTimeTick()` 原始碼

```c
void OSTimeTick (void)
{
    OS_TCB *ptcb;

    OSTimeTickHook();           /* 使用者可自訂的 hook 函式 */

    if (OSRunning == TRUE) {
        ptcb = OSTCBList;
        /* 線性掃描所有 TCB，直到閒置任務為止 */
        while (ptcb->OSTCBPrio != OS_IDLE_PRIO) {
            OS_ENTER_CRITICAL();
            if (ptcb->OSTCBDly != 0) {
                /* 遞減延遲計數器 */
                if (--ptcb->OSTCBDly == 0) {
                    /* 計數到零且未被懸掛（suspend），將任務移至就緒列表 */
                    if ((ptcb->OSTCBStat & OS_STAT_SUSPEND) == OS_STAT_RDY) {
                        OSRdyGrp               |= ptcb->OSTCBBitY;
                        OSRdyTbl[ptcb->OSTCBY] |= ptcb->OSTCBBitX;
                    } else {
                        ptcb->OSTCBDly = 1; /* 仍被懸掛，保持延遲為 1 */
                    }
                }
            }
            ptcb = ptcb->OSTCBNext;
            OS_EXIT_CRITICAL();
        }
    }
}
```

### O(n) 線性掃描 vs. Delta List

`OSTimeTick()` 採用線性掃描所有 TCB 的設計，複雜度為 O(n)。

| 比較項目 | 線性掃描（uC/OS-II 採用） | Delta List（替代方案） |
|------|------|------|
| **時間前進 1 tick** | O(n)（掃描所有 TCB） | O(1)（只更新 delta list 頭部） |
| **插入新的睡眠任務** | O(1)（只設定 `OSTCBDly`） | O(n)（需在有序 delta list 中找插入位置） |
| **實作複雜度** | 低 | 高 |
| **適用場景** | 任務數量少的嵌入式系統 | 任務數量多、tick 頻率高的系統 |

---

## 排程器鎖定（Scheduler Lock）

---

### `OSSchedLock()` / `OSSchedUnlock()` 原始碼

```c
void OSSchedLock (void)
{
    OS_ENTER_CRITICAL();
    if (OSRunning == TRUE) {
        OSLockNesting++;    /* 遞增鎖定計數器，允許巢狀呼叫 */
    }
    OS_EXIT_CRITICAL();
}

void OSSchedUnlock (void)
{
    OS_ENTER_CRITICAL();
    if (OSRunning == TRUE) {
        OSLockNesting--;
        if (OSLockNesting == 0) {
            OS_EXIT_CRITICAL();
            OS_Sched();     /* 計數歸零時立即執行一次排程評估 */
        } else {
            OS_EXIT_CRITICAL();
        }
    } else {
        OS_EXIT_CRITICAL();
    }
}
```

- **`OSLockNesting` 計數器**：允許巢狀呼叫 `OSSchedLock()`；必須對應相同次數的 `OSSchedUnlock()` 才能解鎖。
- **中斷仍有效**：鎖定排程器只阻止任務切換，中斷仍可被接收與處理。
- **禁止事項**：鎖定後不可呼叫任何可能導致情境切換的 API（如 `OSSemPend()`、`OSTimeDly()` 等），否則系統可能死鎖。

### 三種競爭條件防護機制對比

| 機制 | 禁止中斷 | 禁止任務搶占 | 影響範圍 | 典型使用場景 |
|------|------|------|------|------|
| **`OS_ENTER/EXIT_CRITICAL`** | 是 | 是 | 全系統 | 核心程式碼短臨界區 |
| **`OSSchedLock/Unlock`** | 否 | 是 | 所有任務 | 需要中斷回應的較長臨界區 |
| **`OSSemPend/Post`** | 否 | 否 | 只影響 pending/posting 任務 | 使用者程式碼中的共享資源保護 |

### 中斷處理 Do's and Don'ts

**應做（Do's）**：

- **ISR 盡可能短**：ISR 只做最小工作，複雜工作延遲至工作任務（worker task）。
- **長工作交給工作任務**：ISR 透過旗號或訊息通知工作任務處理後續。

**不可做（Don'ts）**：

- **不可在中斷關閉時呼叫系統服務**：可能造成系統掛起或競爭條件。
- **不可在排程器鎖定時呼叫系統服務**：可能造成死鎖。
- **不可在 ISR 中呼叫 blocking API**：會造成死鎖或非預期延遲。

---

## 閒置任務（Idle Task）

---

**閒置任務（Idle Task）**是 uC/OS-II 自動建立的最低優先權任務（priority 63），永遠不可被刪除或懸掛。

```c
void OS_TaskIdle (void *pdata)
{
    pdata = pdata;  /* 防止編譯器 warning */
    for (;;) {
        OS_ENTER_CRITICAL();
        OSIdleCtr++;        /* 遞增閒置計數器，供 CPU 使用率計算用 */
        OS_EXIT_CRITICAL();
        OSTaskIdleHook();   /* 使用者可自訂的 hook（注意：不可呼叫 delay 或 suspend） */
    }
}
```

- **永遠就緒**：當所有其他任務均不在 Ready 狀態時，閒置任務執行，確保 CPU 永遠有任務可跑。
- **`OSIdleCtr`**：閒置計數器由統計任務（Stat Task, priority 62）讀取，計算 CPU 使用率。
- **Hook 限制**：`OSTaskIdleHook()` 中絕對不可呼叫 `OSTimeDly()`、`OSTaskSuspend()` 等 blocking API，否則閒置任務永遠無法恢復執行。

---

## 啟動序列（Startup Sequence）

---

uC/OS-II 的啟動分三個階段：

- **`OSInit()`**：初始化所有核心資料結構（TCB 自由列表、就緒列表、事件控制區塊等），並自動建立閒置任務（`OS_TaskIdle`，priority 63）。
- **建立至少一個應用任務**：在呼叫 `OSStart()` 前，必須以 `OSTaskCreate()` 或 `OSTaskCreateExt()` 建立至少一個任務。
- **`OSStart()`**：找出就緒列表中最高優先權任務，載入其 TCB 的堆疊指標，模擬從中斷返回（`IRET`）開始執行；`OSStart()` 永遠不會返回給 `main()`。

```c
void main (void)
{
    OSInit();                          /* 初始化核心資料結構 */
    OSTaskCreate(StartTask, ...);      /* 建立至少一個任務 */
    OSStart();  /* 啟動多工，此行之後的程式碼永遠不會執行 */
}

void OSStart (void)
{
    if (OSRunning == FALSE) {
        /* 找出就緒列表中最高優先權任務 */
        y             = OSUnMapTbl[OSRdyGrp];
        OSPrioHighRdy = (INT8U)((y << 3) + OSUnMapTbl[OSRdyTbl[y]]);
        OSTCBHighRdy  = OSTCBPrioTbl[OSPrioHighRdy];
        OSTCBCur      = OSTCBHighRdy;
        /* 呼叫 OSStartHighRdy()（組合語言），以 IRET 啟動第一個任務 */
        OSStartHighRdy();
    }
}
```

**設計細節**：新建立的任務堆疊被 `OSTaskStkInit()` 初始化成「剛剛被中斷」的狀態（暫存器預設值壓入堆疊），所以 `OSStart()` 可以用 `IRET` 指令「返回」到任務入口，與普通情境切換使用完全相同的程式路徑。

---

**備註：本筆記整理 uC/OS-II Part 3 的核心結構實作，關鍵貢獻在於以臨界區三機制對比表、O(1) 就緒列表點陣圖操作（OSMapTbl / OSUnMapTbl）、OS_Sched() 與 OSIntExit() 原始碼解析、十步驟 ISR 模板，以及 OSTimeTick() 複雜度分析，完整呈現 uC/OS-II 核心的設計理念與實作細節。**
