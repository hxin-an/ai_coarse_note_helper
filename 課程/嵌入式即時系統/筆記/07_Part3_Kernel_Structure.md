# 嵌入式即時系統 — uCOS Part 3 Kernel Structure

> 來源：`uCOS Part 3 kernel structure.pdf` | 產生日期：2026-03-23

## 前言

---

本份筆記整理 uC/OS-II Part 3 的核心實作細節，從檔案架構、臨界區機制、任務建立與管理，深入到 TCB 資料結構、O(1) 就緒列表、排程器實作、情境切換機制、ISR 十步驟模板、時鐘節拍掃描、排程鎖定，以及啟動序列。相較於 Part 2 的系統概念，Part 3 直接呈現原始碼層面的實作邏輯，是理解 uC/OS-II 可移植性設計與各平台 port 的關鍵材料。

## 大綱

---

- uC/OS-II 檔案架構（五層模型）
- 臨界區（Critical Section）
  - 為何不用旗號保護臨界區
  - 關閉中斷機制（Method 1 vs Method 2）
- 任務結構與管理
  - 任務程式碼格式
  - 任務管理 API
  - 五大任務狀態（詳解）
- 任務控制區塊（`OS_TCB`）
  - 關鍵欄位說明
  - Free List 管理
  - `OS_TCBInit()` 原始碼
- 就緒列表（Ready List）
  - 8×8 點陣圖設計
  - O(1) 加入與移除
  - `OSMapTbl` 與 `OSUnMapTbl`
- 排程器（`OS_Sched()`）
  - 原始碼解析
  - `OS_TASK_SW()` 軟體中斷
- 情境切換機制
  - 任務層級 vs. ISR 層級
  - 情境切換步驟
- ISR 處理（十步驟模板）
  - `OSIntEnter()` / `OSIntExit()` 原始碼
  - `OSIntCtxSw()` vs `OS_TASK_SW()`
- `OSTimeTick()` 實作
  - 線性掃描 O(n)
  - Delta List 改良
- 排程鎖定（`OSSchedLock()` / `OSSchedUnlock()`）
- 閒置任務（`OS_TaskIdle`）
- 啟動序列（`OSInit()` → `OSStart()` → `OSStartHighRdy()`）

## uC/OS-II 檔案架構（五層模型）

---

uC/OS-II 以嚴格的分層架構實現跨平台可移植性，共分五層：

| 層級 | 檔案 / 元件 | 說明 |
|------|------------|------|
| **應用層** | 使用者程式碼 | 任務函式、main()、硬體初始化 |
| **處理器無關核心** | `ucos_ii.c` / `ucos_ii.h` | 排程、TCB、事件管理等核心邏輯；不依賴任何硬體 |
| **核心組態** | `OS_CFG.H` | 編譯期開關：最大任務數、各功能啟用與否、堆疊大小等 |
| **處理器相關 Port** | `OS_CPU.H` / `OS_CPU_A.ASM` / `OS_CPU_C.C` | 情境切換（組語）、資料型別定義、臨界區機制；每個目標平台各有一份 |
| **硬體層** | CPU / BSP | 實體處理器與板級支援套件 |

- **可移植性設計**：移植到新平台只需重新撰寫 Port 層，核心程式碼完全不動。
- **`OS_CFG.H` 的作用**：在編譯期裁剪核心體積，不需要的功能（如記憶體管理、訊息佇列）可直接關閉，減少 ROM/RAM 佔用。

## 臨界區（Critical Section）

---

**臨界區（Critical Section）**是指不可被中斷打斷的程式碼片段，通常存取共用資料結構（如 TCB 鏈表、就緒列表）。若執行到一半被中斷，可能導致資料不一致。

### 為何不用旗號（Semaphore）保護臨界區

- **旗號本身也需要臨界區**：`OSSemPend()` 在修改旗號計數前，本身就需要一種互斥機制；若用旗號保護臨界區，會形成雞生蛋的循環依賴。
- **ISR 不可呼叫 blocking API**：ISR 中不允許呼叫 `OSSemPend()` 等可能阻塞的 API（否則 ISR 可能永遠無法返回），因此旗號無法在 ISR 與任務之間共用保護機制。
- **關閉中斷是唯一正確做法**：透過關閉 CPU 中斷，可同時防止 ISR 與其他任務干擾臨界區，且開銷極小。

### 關閉中斷機制（Method 1 vs Method 2）

uC/OS-II 提供三種 `OS_CRITICAL_METHOD`，x86 port 使用 **Method 2**：

```c
/* Method 2: 使用旗標暫存器（PSW）堆疊推入/彈出 */
#define OS_ENTER_CRITICAL()  asm PUSHF; asm CLI   /* 儲存中斷狀態並關閉中斷 */
#define OS_EXIT_CRITICAL()   asm POPF             /* 還原中斷狀態（可能重新開啟） */
```

- **Method 1 的問題**：直接 `CLI`（關）/ `STI`（開），若呼叫 `OS_EXIT_CRITICAL()` 前原本中斷已是關閉狀態，`STI` 會錯誤地開啟中斷，破壞外層臨界區。
- **Method 2 的優點**：`PUSHF` 儲存當前中斷旗標，`POPF` 還原而非強制開啟，可正確處理巢狀臨界區（outer critical section 不受 inner critical section 的 `POPF` 影響）。

## 任務結構與管理

---

### 任務程式碼格式

uC/OS-II 的任務函式必須符合固定原型，且主體為無限迴圈：

```c
void MyTask(void *pdata)    /* pdata: 建立任務時傳入的參數指標 */
{
    /* 初始化工作（只執行一次） */
    for (;;) {
        /* 任務主體邏輯 */
        OSTimeDly(10);      /* 必須呼叫至少一個 blocking API，讓出 CPU */
    }
}
```

- **強制 blocking 呼叫**：若任務從不呼叫任何 blocking API，它將永遠佔用 CPU，其他低優先權任務永遠無法執行。
- **不可 return**：任務函式一旦返回，核心行為未定義；若需終止任務，應呼叫 `OSTaskDel(OS_PRIO_SELF)`。

### 任務管理 API

| API | 功能 |
|-----|------|
| `OSTaskCreate(task, pdata, stk, prio)` | 建立任務（基本版）；stk 指向堆疊頂端 |
| `OSTaskCreateExt(...)` | 建立任務（擴充版）；額外支援堆疊監控、擴充 TCB 指標 |
| `OSTaskChangePrio(oldprio, newprio)` | 動態修改任務優先權；優先權必須唯一 |
| `OSTaskDel(prio)` | 刪除任務，釋放 TCB 回 free list |
| `OSTaskSuspend(prio)` | 掛起任務（進入額外的 Suspend 狀態） |
| `OSTaskResume(prio)` | 恢復被掛起的任務 |

### 五大任務狀態（詳解）

uC/OS-II 以 `OSTCBStat` 欄位記錄任務狀態，各狀態的內部意義：

- **Dormant（休眠）**：`OSTaskCreate()` 尚未呼叫，或 `OSTaskDel()` 已呼叫；TCB 在 free list 中，不在就緒列表或等待列表。
- **Ready（就緒）**：位於就緒列表（`OSRdyTbl[]`），`OSTCBDly == 0` 且 `OSTCBStat == 0`，等待排程器選中。
- **Running（執行中）**：`OSTCBCur` 指向此任務，當前佔用 CPU；邏輯上等同於處於 Ready 狀態但已被選中執行。
- **Waiting（等待中）**：`OSTCBDly > 0`（計時等待）或 `OSTCBStat != 0`（等待事件）；任務從就緒列表移除，`OSTimeTick()` 或事件發布時才移回。
- **ISR Running（中斷執行中）**：CPU 正執行 ISR；`OSIntNesting > 0`；被中斷任務的情境儲存在其堆疊中，等待 ISR 結束後恢復。

## 任務控制區塊（`OS_TCB`）

---

**任務控制區塊（Task Control Block, TCB）**是核心追蹤任務執行狀態的核心資料結構，每個任務對應一個 `OS_TCB` 實例。

### 關鍵欄位說明

| 欄位 | 型別 | 說明 |
|------|------|------|
| `OSTCBStkPtr` | `OS_STK *` | 指向任務堆疊頂端（情境切換時的存取點） |
| `OSTCBExtPtr` | `void *` | 使用者自定擴充資料指標（可掛載任意結構） |
| `OSTCBStkBottom` | `OS_STK *` | 堆疊底端（用於堆疊溢位偵測） |
| `OSTCBStkSize` | `INT32U` | 堆疊大小（`OSTaskStkChk()` 使用） |
| `OSTCBOpt` | `INT16U` | 建立選項旗標（如 `OS_TASK_OPT_SAVE_FP`、`OS_TASK_OPT_STK_CHK`） |
| `OSTCBId` | `INT16U` | 任務 ID（`OSTaskCreateExt()` 專用） |
| `OSTCBNext` / `OSTCBPrev` | `OS_TCB *` | 雙向鏈結串列指標（串接所有已建立的 TCB） |
| `OSTCBEventPtr` | `OS_EVENT *` | 指向任務正在等待的事件控制區塊（ECB） |
| `OSTCBMsg` | `void *` | 直接傳遞的訊息指標（用於 mailbox） |
| `OSTCBDly` | `INT32U` | 剩餘等待節拍數；`OSTimeTick()` 每次遞減，歸零時移回就緒列表 |
| `OSTCBStat` | `INT8U` | 任務狀態旗標（0 = Ready，非 0 = 等待某事件） |
| `OSTCBPrio` | `INT8U` | 任務優先權（0–63） |
| `OSTCBX` / `OSTCBY` | `INT8U` | 就緒列表的 bit 位置（`X = prio & 0x07`，`Y = prio >> 3`） |
| `OSTCBBitX` / `OSTCBBitY` | `INT8U` | 對應的位元遮罩（`OSMapTbl[X]`、`OSMapTbl[Y]`） |
| `OSTCBDelReq` | `INT8U` | 外部刪除請求旗標（`OSTaskDelReq()` 使用） |

### Free List 管理

- **初始化**：`OSInit()` 呼叫時，核心將所有 `OS_MAX_TASKS` 個 TCB 以 `OSTCBNext` 串接成單向 free list，`OSTCBFreeList` 指向串列頭。
- **建立任務時**：從 `OSTCBFreeList` 取出一個 TCB，填入任務資訊，加入雙向的已建立 TCB 鏈（`OSTCBList`）。
- **刪除任務時**：將 TCB 從 `OSTCBList` 摘除，歸還至 `OSTCBFreeList` 頭部。

### `OS_TCBInit()` 原始碼解析

```c
INT8U OS_TCBInit(INT8U prio, OS_STK *ptos, OS_STK *pbos,
                 INT16U id, INT32U stk_size,
                 void *pext, INT16U opt)
{
    OS_TCB *ptcb;

    OS_ENTER_CRITICAL();                      /* 進入臨界區 */
    ptcb = OSTCBFreeList;                     /* 從 free list 取出 TCB */
    if (ptcb != (OS_TCB *)0) {
        OSTCBFreeList = ptcb->OSTCBNext;      /* 更新 free list 頭 */
        OS_EXIT_CRITICAL();                   /* 離開臨界區（越早越好） */

        ptcb->OSTCBStkPtr  = ptos;           /* 儲存堆疊頂端指標 */
        ptcb->OSTCBPrio    = prio;
        ptcb->OSTCBStat    = OS_STAT_RDY;    /* 初始狀態：就緒 */
        ptcb->OSTCBDly     = 0;
        ptcb->OSTCBExtPtr  = pext;
        ptcb->OSTCBStkBottom = pbos;
        ptcb->OSTCBStkSize   = stk_size;
        ptcb->OSTCBOpt       = opt;
        ptcb->OSTCBId        = id;

        /* 計算就緒列表位置 */
        ptcb->OSTCBY   = prio >> 3;                  /* Y = prio / 8 */
        ptcb->OSTCBBitY = OSMapTbl[ptcb->OSTCBY];
        ptcb->OSTCBX   = prio & 0x07;                /* X = prio % 8 */
        ptcb->OSTCBBitX = OSMapTbl[ptcb->OSTCBX];

        OS_ENTER_CRITICAL();
        /* 插入雙向鏈 OSTCBList */
        ptcb->OSTCBNext = OSTCBList;
        if (OSTCBList != (OS_TCB *)0)
            OSTCBList->OSTCBPrev = ptcb;
        OSTCBList = ptcb;
        ptcb->OSTCBPrev = (OS_TCB *)0;

        /* 加入就緒列表 */
        OSRdyGrp        |= ptcb->OSTCBBitY;
        OSRdyTbl[ptcb->OSTCBY] |= ptcb->OSTCBBitX;
        OS_EXIT_CRITICAL();
        return OS_NO_ERR;
    }
    OS_EXIT_CRITICAL();
    return OS_NO_MORE_TCB;                    /* TCB 已耗盡 */
}
```

- **關鍵設計**：先縮短第一個臨界區（只取 TCB），再以第二個臨界區修改共用結構；避免持鎖時間過長影響中斷延遲。

## 就緒列表（Ready List）

---

**就緒列表（Ready List）**使用 8×8 點陣圖設計，以 O(1) 時間找出最高優先權就緒任務，是 uC/OS-II 排程效率的核心。

### 8×8 點陣圖設計

- **`OSRdyGrp`**：8-bit 整數，每個 bit 對應一個「組」（group）；若某組中有任何就緒任務，對應 bit 為 1。
- **`OSRdyTbl[8]`**：長度 8 的陣列，每個元素為 8-bit 整數，對應各組內的 8 個優先權 bit。
- **優先權對應**：優先權 `prio` 對應到 `OSRdyTbl[prio >> 3]` 的第 `(prio & 0x07)` 個 bit。

```
OSRdyGrp:        bit7  bit6  bit5  bit4  bit3  bit2  bit1  bit0
                  ↕     ↕     ↕     ↕     ↕     ↕     ↕     ↕
OSRdyTbl[0..7]: [p7-0][p15-8][p23-16][p31-24][p39-32][p47-40][p55-48][p63-56]
```

### O(1) 加入與移除

**加入任務（設為就緒）**：

```c
OSRdyGrp              |= OSMapTbl[prio >> 3];  /* 標記組 */
OSRdyTbl[prio >> 3]   |= OSMapTbl[prio & 0x07]; /* 標記組內 bit */
```

**移除任務（移出就緒）**：

```c
if ((OSRdyTbl[prio >> 3] &= ~OSMapTbl[prio & 0x07]) == 0)
    OSRdyGrp &= ~OSMapTbl[prio >> 3];  /* 整組清空才清除 group bit */
```

**找出最高優先權就緒任務**：

```c
y = OSUnMapTbl[OSRdyGrp];                  /* 找最高優先權非空的組 */
x = OSUnMapTbl[OSRdyTbl[y]];              /* 找組內最高優先權 */
OSPrioHighRdy = (y << 3) + x;             /* 合成優先權數值 */
```

### `OSMapTbl` 與 `OSUnMapTbl`

- **`OSMapTbl[8]`**：將索引 0–7 對應至對應的 bit 遮罩（`{0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}`）。
- **`OSUnMapTbl[256]`**：256 元素的查找表，輸入一個 8-bit 值，輸出其最低有效位（LSB）的位置（0–7）；這等同於 O(1) 的 find-lowest-set-bit 操作，避免逐 bit 掃描。

## 排程器（`OS_Sched()`）

---

`OS_Sched()` 是 uC/OS-II 的任務層級排程器，在每次可能影響任務優先序的事件後被呼叫（如 `OSSemPost()`、`OSTimeDly()` 返回等）。

### 原始碼解析

```c
void OS_Sched(void)
{
    INT8U y;
    OS_ENTER_CRITICAL();

    /* 僅在非 ISR、排程未鎖定時才排程 */
    if (OSIntNesting == 0 && OSLockNesting == 0) {
        y = OSUnMapTbl[OSRdyGrp];                      /* 找最高優先權就緒組 */
        OSPrioHighRdy = (INT8U)((y << 3) +
                        OSUnMapTbl[OSRdyTbl[y]]);      /* 計算最高優先權 */

        if (OSPrioHighRdy != OSPrioCur) {              /* 需要切換才執行 */
            OSTCBHighRdy = OSTCBPrioTbl[OSPrioHighRdy]; /* 取目標 TCB */
            OSCtxSwCtr++;                               /* 統計計數器 */
            OS_TASK_SW();                               /* 觸發情境切換 */
        }
    }
    OS_EXIT_CRITICAL();
}
```

- **`OSIntNesting == 0`**：確保不在 ISR 中（ISR 使用 `OSIntExit()` 觸發排程）。
- **`OSLockNesting == 0`**：確保排程未被 `OSSchedLock()` 鎖定。
- **`OSPrioHighRdy != OSPrioCur`**：只有在最高優先權任務改變時才執行情境切換，避免不必要的切換開銷。

### `OS_TASK_SW()` 軟體中斷

```c
#define OS_TASK_SW()  asm INT 80h
```

- **機制**：觸發軟體中斷 80h，CPU 跳至對應的中斷服務常式執行情境切換。
- **設計原因**：透過軟體中斷統一情境切換的入口，使任務層級切換（`OS_TASK_SW()`）與 ISR 層級切換（`OSIntCtxSw()`）共用相同的暫存器儲存/還原框架，但起點不同。

## 情境切換機制

---

### 任務層級 vs. ISR 層級

| 切換類型 | 觸發點 | 使用函式 | 起點差異 |
|----------|--------|----------|---------|
| **任務層級** | `OS_Sched()` 內部 | `OS_TASK_SW()` | 需完整儲存所有暫存器 |
| **ISR 層級** | `OSIntExit()` 內部 | `OSIntCtxSw()` | ISR 已儲存部分暫存器，跳過重複儲存 |

### 情境切換步驟（任務層級）

1. **儲存 LPT（低優先權任務）情境**：將所有 CPU 暫存器壓入 LPT 的堆疊。
2. **更新 `OSTCBCur->OSTCBStkPtr`**：將 LPT 的當前堆疊指標（SP）儲存至其 TCB，供下次恢復使用。
3. **`OSTCBCur = OSTCBHighRdy`**：更新全域指標指向新的執行任務。
4. **`OSPrioCur = OSPrioHighRdy`**：更新當前優先權記錄。
5. **載入 HPT（高優先權任務）的 `OSTCBStkPtr`**：從 HPT 的 TCB 取出堆疊指標，設定 SP。
6. **還原 HPT 情境**：從 HPT 的堆疊彈出所有暫存器。
7. **`IRET`**：CPU 跳至 HPT 上次被中斷的位置繼續執行。

## ISR 處理（十步驟模板）

---

uC/OS-II 的 ISR 必須遵循以下十步驟模板，以確保核心資料結構的一致性：

```asm
; 步驟 1：儲存所有 CPU 暫存器
PUSHALL

; 步驟 2：呼叫 OSIntEnter()，遞增 OSIntNesting
CALL OSIntEnter

; 步驟 3：若 OSIntNesting == 1（最外層中斷），儲存 SP 至 OSTCBCur->OSTCBStkPtr
;         巢狀中斷不儲存（每個任務只有一個 TCB，只需最初的堆疊指標）
CMP OSIntNesting, 1
JNE skip_sp_save
MOV [OSTCBCur->OSTCBStkPtr], SP
skip_sp_save:

; 步驟 4–8：使用者 ISR 程式碼（讀取裝置、發布事件等）
CALL UserISRCode

; 步驟 9：呼叫 OSIntExit()，遞減 OSIntNesting；若歸零且有更高優先權任務就緒，
;         改為呼叫 OSIntCtxSw() 觸發任務切換
CALL OSIntExit

; 步驟 10：還原所有 CPU 暫存器，執行 IRET
POPALL
IRET
```

### `OSIntEnter()` / `OSIntExit()` 原始碼解析

```c
void OSIntEnter(void)
{
    OS_ENTER_CRITICAL();
    OSIntNesting++;          /* 遞增巢狀計數器 */
    OS_EXIT_CRITICAL();
}

void OSIntExit(void)
{
    OS_ENTER_CRITICAL();
    if (--OSIntNesting == 0) {                          /* 最外層 ISR 結束 */
        if (OSLockNesting == 0) {                       /* 排程未鎖定 */
            INT8U y = OSUnMapTbl[OSRdyGrp];
            OSPrioHighRdy = (INT8U)((y << 3) +
                            OSUnMapTbl[OSRdyTbl[y]]);
            if (OSPrioHighRdy != OSPrioCur) {           /* 有更高優先權任務 */
                OSTCBHighRdy = OSTCBPrioTbl[OSPrioHighRdy];
                OSCtxSwCtr++;
                OSIntCtxSw();                           /* ISR 層級情境切換 */
            }
        }
    }
    OS_EXIT_CRITICAL();
}
```

### `OSIntCtxSw()` vs `OS_TASK_SW()`

- **`OS_TASK_SW()`**：觸發軟體中斷，CPU 完整儲存暫存器後再進行切換；用於任務層級（正常執行流中）。
- **`OSIntCtxSw()`**：ISR 已儲存暫存器，跳過儲存步驟直接切換至高優先權任務的堆疊；用於 ISR 層級，避免雙重儲存。

## `OSTimeTick()` 實作

---

`OSTimeTick()` 在每個時鐘節拍中斷的 ISR 中被呼叫，負責更新所有任務的延遲計數器。

### 線性掃描 O(n) 實作

```c
void OSTimeTick(void)
{
    OS_TCB *ptcb = OSTCBList;    /* 從已建立 TCB 鏈的頭部開始 */
    while (ptcb->OSTCBPrio != OS_IDLE_PRIO) {
        OS_ENTER_CRITICAL();
        if (ptcb->OSTCBDly != 0) {          /* 有延遲計數 */
            if (--ptcb->OSTCBDly == 0) {    /* 計數歸零 */
                if (!(ptcb->OSTCBStat & OS_STAT_SUSPEND)) {
                    /* 不是 Suspend 狀態，移回就緒列表 */
                    OSRdyGrp           |= ptcb->OSTCBBitY;
                    OSRdyTbl[ptcb->OSTCBY] |= ptcb->OSTCBBitX;
                } else {
                    ptcb->OSTCBDly = 1;     /* Suspend 任務，恢復計數為 1 */
                }
            }
        }
        OS_EXIT_CRITICAL();
        ptcb = ptcb->OSTCBNext;
    }
}
```

- **複雜度**：O(n)，n 為系統中所有已建立的任務數量；任務數多時，時鐘節拍 ISR 開銷線性增長。

### Delta List 改良（概念）

- **問題**：O(n) 掃描在任務數量大時效率低下，時鐘節拍 ISR 執行時間不穩定。
- **Delta List**：將等待任務按剩餘延遲時間排序，每個節點只儲存與前一個節點的差值（delta）；`OSTimeTick()` 只需更新串列頭，達到 O(1) 更新、O(1) 到期任務識別。
- **uC/OS-II 原生實作**：未內建 Delta List，屬於進階改良方向；若任務數量少（嵌入式系統常見），O(n) 掃描足夠。

## 排程鎖定（`OSSchedLock()` / `OSSchedUnlock()`）

---

**排程鎖定**允許任務暫時禁止排程器切換任務，但不關閉中斷（ISR 仍可執行）。

```c
void OSSchedLock(void)
{
    if (OSRunning) {
        OS_ENTER_CRITICAL();
        OSLockNesting++;     /* 遞增鎖定計數器 */
        OS_EXIT_CRITICAL();
    }
}

void OSSchedUnlock(void)
{
    if (OSRunning) {
        OS_ENTER_CRITICAL();
        if (OSLockNesting > 0) {
            if (--OSLockNesting == 0) {  /* 計數歸零才真正解鎖 */
                OS_EXIT_CRITICAL();
                OS_Sched();              /* 立即觸發一次排程評估 */
                return;
            }
        }
        OS_EXIT_CRITICAL();
    }
}
```

- **使用場景**：存取需要多步驟修改的非原子資料結構，但不希望關閉中斷（例如更新顯示緩衝區，允許 UART ISR 繼續執行）。
- **與關閉中斷的區別**：排程鎖定期間 ISR 仍可執行，中斷延遲不受影響；關閉中斷則完全阻止 ISR 執行，應盡量縮短持鎖時間。
- **三種競態避免機制總結**：

| 機制 | 阻止對象 | 適用情境 |
|------|---------|---------|
| 關閉中斷（`OS_ENTER_CRITICAL`） | 所有中斷 + 排程器 | 核心資料結構的原子操作 |
| 排程鎖定（`OSSchedLock`） | 排程器（ISR 仍執行） | 需要原子操作但不能關中斷的場景 |
| 旗號/互斥鎖（Semaphore/Mutex） | 其他任務（ISR 視情況） | 應用層的資源保護 |

## 閒置任務（`OS_TaskIdle`）

---

**閒置任務（Idle Task）**由 `OSInit()` 自動建立，優先權固定為 63（最低），在系統無其他就緒任務時獨佔 CPU。

```c
void OS_TaskIdle(void *pdata)
{
    pdata = pdata;    /* 防止編譯器警告（unused parameter） */
    for (;;) {
        OS_ENTER_CRITICAL();
        OSIdleCtr++;  /* 遞增閒置計數器，供 CPU 使用率計算 */
        OS_EXIT_CRITICAL();
        OSTaskIdleHook();  /* 可由使用者定義的 Hook（如進入省電模式） */
    }
}
```

- **`OSIdleCtr` 的用途**：統計任務（Stat Task，優先權 62）定期讀取 `OSIdleCtr`，與全滿負載的基準值比較，計算 CPU 使用率百分比。
- **必要性**：確保在任何情況下都有任務可執行，避免排程器無任務可選的邊界情況。

## 啟動序列（`OSInit()` → `OSStart()` → `OSStartHighRdy()`）

---

uC/OS-II 的啟動分三個階段：

### 階段 1：`OSInit()`（核心初始化）

```c
void OSInit(void)
{
    /* 初始化所有核心資料結構 */
    OS_InitMisc();      /* 全域變數清零 */
    OS_InitRdyList();   /* 就緒列表清零 */
    OS_InitTCBList();   /* TCB free list 建立 */
    OS_InitEventList(); /* ECB free list 建立 */

    /* 建立閒置任務（優先權 63） */
    OSTaskCreate(OS_TaskIdle, (void *)0,
                 &OSTaskIdleStk[OS_IDLE_STK_SIZE-1], OS_IDLE_PRIO);

    /* 若啟用統計任務，建立統計任務（優先權 62） */
    #if OS_TASK_STAT_EN
    OSTaskCreate(OS_TaskStat, ...);
    #endif
}
```

### 階段 2：`OSStart()`（啟動排程）

```c
void OSStart(void)
{
    if (!OSRunning) {
        INT8U y = OSUnMapTbl[OSRdyGrp];
        OSPrioHighRdy = (INT8U)((y << 3) +
                        OSUnMapTbl[OSRdyTbl[y]]);  /* 找最高優先權就緒任務 */
        OSPrioCur    = OSPrioHighRdy;
        OSTCBHighRdy = OSTCBPrioTbl[OSPrioHighRdy];
        OSTCBCur     = OSTCBHighRdy;
        OSStartHighRdy();   /* 永不返回 */
    }
}
```

- **在 `OSInit()` 之後、`OSStart()` 之前**：使用者可呼叫 `OSTaskCreate()` 建立初始任務，但不可啟動時鐘節拍中斷。

### 階段 3：`OSStartHighRdy()`（處理器相關，Port 層實作）

```asm
OSStartHighRdy:
    MOV  [OSRunning], 1          ; 設定 OSRunning = TRUE
    ; 載入 OSTCBHighRdy->OSTCBStkPtr 至 SP
    MOV  SP, [OSTCBHighRdy->OSTCBStkPtr]
    POPALL                        ; 還原所有暫存器（模擬從堆疊恢復）
    IRET                          ; 跳至第一個任務的入口點
```

- **設計巧妙之處**：`OSTaskCreate()` 在建立任務時，`OSTaskStkInit()` 會在堆疊上預置一組「假情境」（fake context），使得 `OSStartHighRdy()` 的 `POPALL + IRET` 可以正確跳至任務函式的入口，彷彿從一次中斷返回。

**備註：本筆記整理 uC/OS-II Part 3 的核心實作，核心貢獻在於系統化呈現從 TCB free list、O(1) 點陣圖就緒列表、OS_Sched() 排程器、任務層級與 ISR 層級情境切換，到十步驟 ISR 模板與三段式啟動序列的完整實作邏輯，是理解 uC/OS-II 可移植性設計與底層排程機制的關鍵參考。**
