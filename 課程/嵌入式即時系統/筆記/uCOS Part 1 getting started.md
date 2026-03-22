# 嵌入式即時系統 — uC/OS-II Part 1: Getting Started
> 來源：`uCOS Part 1 getting started.pdf` | 產生日期：2026-03-21

## 前言

uC/OS-II 是一個輕量開源的即時作業系統核心（RTOS），記憶體佔用約 20KB，支援搶佔式優先權排程，可移植至 x86、ARM、MIPS 等多種平台。本章以三個由淺入深的範例說明如何從零開始撰寫一個 uC/OS-II 程式：如何初始化核心、建立任務（task）、以及利用 Semaphore、Mailbox、Message Queue 進行 Inter-Task Communication（IPC）。理解這套啟動流程與 API 是往後學習 RTOS 排程、中斷處理與記憶體管理的基礎。

## 大綱

- [uC/OS-II 概述](#ucOS-II-概述)
- [程式骨架總覽](#程式骨架總覽)
- [初始化與啟動流程（main() → OSStart()）](#初始化與啟動流程)
  - [OSInit()](#osinit)
  - [PC_DOSSaveReturn()](#pc_dossavereturn)
  - [PC_VectSet() — Context Switch Handler](#pc_vectset--context-switch-handler)
  - [OSTaskCreate()](#ostaskcreate)
  - [OSStart()](#osstart)
- [TaskStart() — 啟動任務](#taskstart--啟動任務)
  - [Tick ISR 安裝與中斷向量表修改](#tick-isr-安裝與中斷向量表修改)
  - [OS_ENTER_CRITICAL / OS_EXIT_CRITICAL](#os_enter_critical--os_exit_critical)
- [任務（Task）](#任務task)
  - [任務建立：OSTaskCreate vs OSTaskCreateExt](#任務建立ostaskcreate-vs-ostaskcreateext)
  - [任務堆疊（Stack）管理](#任務堆疊stack管理)
  - [浮點運算的堆疊保留](#浮點運算的堆疊保留)
- [IPC 機制](#ipc-機制)
  - [Semaphore](#semaphore)
  - [Mailbox](#mailbox)
  - [Message Queue](#message-queue)
- [Hooks — 系統事件回呼](#hooks--系統事件回呼)
- [三個範例總結](#三個範例總結)

---

## uC/OS-II 概述

**uC/OS-II**（Micro C OS version 2）是由 Jean J. Labrosse 撰寫的開源即時核心：

| 特性 | 值 |
|------|-----|
| 記憶體佔用 | ~20KB（完整核心） |
| 排程策略 | 搶佔式優先權（Preemptive Priority-Driven） |
| 最大任務數 | 62 個使用者任務 |
| 支援平台 | x86, 68x, ARM, MIPS, … |

「即時」的意義：系統保證**最高優先權的就緒任務**在可預測的時間內取得 CPU → 適合對時序有嚴格要求的嵌入式應用。

---

## 程式骨架總覽

一個最小的 uC/OS-II 程式需要三個檔案：

| 檔案 | 用途 |
|------|------|
| `test.c` | 主程式（main、任務函數） |
| `os_cfg.h` | 核心設定（任務數、stack 大小、功能開關） |
| `includes.h` | 統一 include 入口 |

開發環境（投影片範例）：Borland C++ V3.1+ + DOSBox（x86 real mode）。

---

## 初始化與啟動流程

`main()` 的呼叫順序固定，每一步都有明確目的：

```c
void main(void) {
    PC_DispClrScr(...);          // (1) 清螢幕
    OSInit();                    // (2) 初始化 uC/OS-II 核心
    PC_DOSSaveReturn();          // (3) 儲存 DOS 環境（供結束時復原）
    PC_VectSet(uCOS, OSCtxSw);   // (4) 安裝 context switch handler
    RandomSem = OSSemCreate(1);  // (5) 建立 binary semaphore
    OSTaskCreate(TaskStart, ...);// (6) 建立啟動任務
    OSStart();                   // (7) 開始多工（永不返回）
}
```

### OSInit()

**功能**：初始化核心所有內部資料結構，並建立兩個系統任務。

初始化的資料結構：
- **Task Ready List**：記錄哪些任務處於就緒狀態（bitmap 結構，查找 O(1)）
- **Priority Table**（`OSRdyTbl[]`）：每個 priority 的就緒狀態
- **Task Control Blocks（TCB）**：每個任務的控制區塊（priority、stack pointer、state…）
- **Free Pool**（`OSTCBFreeList`）：可用 TCB 的 free list

建立的系統任務：
- **Idle Task**：CPU 閒置時執行（防止 CPU 無事可做）
- **Statistics Task**：統計 CPU 使用率與各任務的 stack 使用量

> 補充：`OSInit()` 之後核心結構就位，但排程尚未啟動，`OSStart()` 才真正開始 context switch。

### PC_DOSSaveReturn()

```c
void PC_DOSSaveReturn(void) {
    PC_ExitFlag  = FALSE;
    OSTickDOSCtr = 8;
    PC_TickISR   = PC_VectGet(VECT_TICK);   // (3) 取得並備份原本的 DOS tick handler
    OS_ENTER_CRITICAL();
    PC_VectSet(VECT_DOS_CHAIN, PC_TickISR); // (4) 把舊 handler 移到另一個 vector
    OS_EXIT_CRITICAL();
    setjmp(PC_JumpBuf);                      // (5) 設定返回點
    if (PC_ExitFlag == TRUE) {
        PC_SetTickRate(18);                  // (6) 恢復 18.2 Hz
        PC_VectSet(VECT_TICK, PC_TickISR);  // (7) 恢復 DOS tick handler
        exit(0);
    }
}
```

**用途**：
1. 備份 DOS 的 tick ISR（原為 18.2Hz）到另一個 vector（供後續 DOS chaining 使用）
2. 透過 `setjmp()` 設定全域返回點 → 當 uC/OS-II 呼叫 `PC_DOSReturn()` 時，`longjmp()` 跳回這裡，還原 DOS 環境並 `exit(0)`

### PC_VectSet() — Context Switch Handler

```c
PC_VectSet(uCOS, OSCtxSw);
```

這行把 IVT[0x80] 的跳轉目標設為 `OSCtxSw`，專門處理 **Voluntary（主動）** Context Switch。

Context Switch 有兩條觸發路徑：

| | Voluntary（主動） | Involuntary（被動） |
| :--- | :--- | :--- |
| **觸發者** | 任務自己（呼叫 `OSSemPend`、`OSTimeDly` 等 blocking 函數） | Timer ISR（`OSTickISR`） |
| **機制** | 函數內部執行 `INT 0x80` → CPU 查 IVT → 跳到 `OSCtxSw` | `OSTickISR` 結束前直接呼叫 `OSIntCtxSw` |
| **任務知道嗎？** | 知道（自己主動讓出 CPU） | 不知道（被強制切走） |

→ 這行只負責設定 Voluntary 那條路。若沒設，任務呼叫 blocking 函數時 CPU 會跳到 DOS 預設的 0x80 中斷，Context Switch 完全失效。Involuntary 那條路由 Timer ISR 直接呼叫 `OSIntCtxSw`，不經過 IVT。

### OSTaskCreate()

```c
OSTaskCreate(
    TaskStart,                        // 任務入口（函數指標）
    (void *)0,                        // 傳給任務的資料（void*）
    &TaskStartStk[TASK_STK_SIZE-1],  // Stack 頂端（x86 向下長）
    0                                 // Priority（0 = 最高）
);
```

- 任務建立後立即進入 **ready** 狀態
- 此時排程尚未啟動，`OSStart()` 之後才會真正執行

### OSStart()

```c
OSStart();  // 永不返回
```

- 以 context switch 方式跳入**最高優先權的就緒任務**
- 進入後就是多工環境，`main()` 的 stack frame 被拋棄
- **重要**：tick ISR 應在 `OSStart()` 之後才安裝（在 startup task 裡），因為 `OSStart()` 呼叫後才有 context switch 能力

---

## TaskStart() — 啟動任務

TaskStart 是優先權最高的使用者任務，負責完成核心啟動後的第二階段初始化：

```c
void TaskStart(void *pdata) {
    OS_ENTER_CRITICAL();
    PC_VectSet(0x08, OSTickISR);       // 安裝 uC/OS-II tick ISR
    PC_SetTickRate(OS_TICKS_PER_SEC); // 改頻率為 200 Hz
    OS_EXIT_CRITICAL();

    OSStatInit();                      // 初始化統計任務
    TaskStartCreateTasks();            // 建立所有應用任務

    for (;;) {
        TaskStartDisp();               // 更新顯示
        if (PC_GetKey(&key) == TRUE)
            if (key == 0x1B) PC_DOSReturn();
        OSCtxSwCtr = 0;
        OSTimeDlyHMSM(0, 0, 1, 0);   // 等待 1 秒
    }
}
```

### Tick ISR 安裝與中斷向量表修改

安裝前後的 Interrupt Vector Table（IVT）變化：

| Vector | 安裝前 | 安裝後 |
|--------|--------|--------|
| 0x08 | DOS Tick Handler（18.2 Hz） | **OSTickISR（200 Hz）**；每 11 ticks 執行一次 INT 0x81（呼叫舊 DOS handler） |
| 0x71 | Undefined | **OSCtxSw** |
| 0x81 | Undefined | **DOS Tick Handler**（chaining 用） |

→ uC/OS-II 把 tick 頻率從 18.2Hz 提升到 200Hz，提高排程解析度；同時保留 DOS chaining 確保相容性。

### OS_ENTER_CRITICAL / OS_EXIT_CRITICAL

**作用**：在單處理器系統上，透過關閉可遮蔽中斷（maskable interrupts）實現 critical section。

| 平台 | 指令 |
|------|------|
| x86 (real mode) | `CLI` / `STI` |
| ARM | `CPSID` / `CPSIE` |

**與 Semaphore 的差異**：Critical section 直接關中斷，期間不可能被搶佔；Semaphore 則是核心管理的等待機制，持有 semaphore 的任務仍可被更高優先任務搶佔。

---

## 任務（Task）

**Task** 是 uC/OS-II 的基本執行單元：

- 擁有獨立的 **Priority、CPU registers、Stack、housekeeping status**
- 最多 62 個使用者任務（priority 0~61，數字越小優先權越高）
- 重新排程點（Rescheduling Points）：
  - Clock tick（timer ISR 返回）
  - Interrupt return
  - Semaphore / Mailbox / Queue 操作

### 任務建立：OSTaskCreate vs OSTaskCreateExt

**OSTaskCreate（基本版）**：
```c
OSTaskCreate(
    Task,           // 函數指標
    (void *)0,      // 使用者資料
    &TaskStk[SIZE-1], // Top of Stack
    priority        // 優先權
);
```

**OSTaskCreateExt（擴充版）**：
```c
OSTaskCreateExt(
    TaskStart,
    (void *)0,
    ptos,               // Top of Stack
    TASK_START_PRIO,
    TASK_START_ID,      // 任務 ID
    pbos,               // Bottom of Stack（供 stack check 用）
    size,               // Stack 大小
    (void *)0,
    OS_TASK_OPT_STK_CHK | OS_TASK_OPT_STK_CLR  // 啟用 stack 檢查與清零
);
```

`OS_TASK_OPT_STK_CHK`：啟用 stack overflow 檢查
`OS_TASK_OPT_STK_CLR`：建立時將 stack 清零（方便計算 stack 使用量）

### 任務堆疊（Stack）管理

```
LOW MEMORY
  ┌─────────────────┐ ← OSTCBStkBottom（.OSTCBStkBottom）
  │   Free Space    │
  │                 │ ← 最深的 Stack 成長點（.OSTCBStkSize 衡量）
  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│ ← Current Stack Pointer
  │   Used Space    │
  └─────────────────┘ ← Initial TOS（傳給 OSTaskCreate 的位址）
HIGH MEMORY
```

Stack 儲存的內容：
- **區域變數**（local variables）
- **函數呼叫的返回位址**（procedure call frames）
- **ISR 的臨時儲存**（ISR 使用被中斷任務的 stack）→ 因此 ISR 會消耗使用者任務的 stack 空間

**Stack Overflow 檢查**（`OSTaskStkCheck()`）：
- 條件：`bos < (tos - stack_length)` → 已使用超過配置量
- 呼叫時機：任務建立時 或 手動呼叫 `OSTaskStkCheck()`
- **不會自動持續檢查**（no automatic stack checking）

### 浮點運算的堆疊保留

若任務使用浮點運算，需在 Stack 中預留空間給浮點函式庫（context switch 時需保存 FP registers）：

```c
OSTaskStkInit_FPE_x86(&ptos, &pbos, &size);
```

傳入原始的 top、bottom、size → 返回後參數被修改，部分 stack 空間被保留給 FP 函式庫。

---

## IPC 機制

### Semaphore

```c
OS_EVENT *sem = OSSemCreate(1);  // 初始值 1 → binary semaphore（互斥用）
OSSemPend(sem, 0, &err);         // P 操作
OSSemPost(sem);                  // V 操作
```

**內部邏輯**：

| 操作 | 動作 |
|------|------|
| `OSSemPend` | counter--；若 < 0 → 任務立即被阻塞並移入 wait list；可設定 timeout |
| `OSSemPost` | counter++；若 ≥ 0 → 從 wait list 中取出一個任務放回 ready list；若有更高優先任務就緒則立即搶佔 |

**使用情境（本例）**：保護 C 標準函式庫的 `random()` 函式（它內部使用全域變數 $a_n = (a_{n-1} \times p + q) \mod m$，為 non-reentrant）→ 一次只讓一個任務呼叫。

### Mailbox

```c
OS_EVENT *mbox = OSMboxCreate(NULL);
OSMboxPost(mbox, (void *)msg);   // 存入一個訊息
msg = OSMboxPend(mbox, 0, &err); // 取出訊息
```

**特性**：
- 儲存**一個訊息**（data pointer）+ wait list
- `OSMboxPost`：若 mailbox 已有訊息 → 回傳錯誤（**不覆蓋**）；若有任務在等待 → 喚醒優先權最高者並觸發排程
- `OSMboxPend`：若 mailbox 空 → 立即被阻塞；可設定 timeout

**Mailbox vs Semaphore**：Mailbox 傳遞資料指標，Semaphore 只傳遞計數（信號）。

### Message Queue

```c
OS_EVENT *q = OSQCreate(&MsgQueueTbl[0], 20); // 建立容量 20 的 queue
OSQPost(q, (void *)msg);    // 加入訊息
msg = OSQPend(q, 0, &err);  // 取出訊息
```

**特性**：

| | Mailbox | Message Queue |
|--|---------|--------------|
| 容量 | 1 則訊息 | N 則訊息（array） |
| 順序 | — | **FIFO** |
| 滿時 Post | 回傳錯誤 | 回傳錯誤（**不阻塞**） |
| 空時 Pend | 阻塞 | 阻塞 |

- 多個任務可同時 pend/post 到同一個 queue
- Queue 滿時 `OSQPost` 直接返回（sender 不被阻塞）→ 需注意訊息遺失

---

## Hooks — 系統事件回呼

**Hook** 是在特定系統事件發生後被呼叫的 callback 函式，讓使用者程式可以監控系統行為：

```c
// 在 context switch 時被呼叫：
void OSTaskSwHook(void) {
    // 計算任務執行時間等...
}
```

uC/OS-II 提供的可客製化 hooks：

| Hook 名稱 | 觸發時機 |
|-----------|---------|
| `OSInitHookBegin/End` | `OSInit()` 開始/結束時 |
| `OSTaskCreateHook` | 任務建立時（傳入 TCB 指標） |
| `OSTaskDelHook` | 任務刪除時 |
| `OSTaskIdleHook` | Idle Task 執行時 |
| `OSTaskStatHook` | Statistics Task 執行時 |
| `OSTaskSwHook` | 每次 context switch 時 |
| `OSTCBInitHook` | TCB 初始化時 |
| `OSTimeTickHook` | 每個 tick 時 |

**注意**：Hooks 在**編譯期**決定（寫在預定義函式體內），**不支援**執行期的 register/deregister → 彈性比 Linux 的 notifier chain 低，但開銷更小，適合 RTOS 的確定性需求。

---

## 三個範例總結

### Example 1 — 基本任務與 Semaphore

- 13 個並行任務（2 內部 + 1 startup + 10 worker）
- Worker tasks 用 semaphore 保護 `random()`
- **重點**：OSInit() → PC_DOSSaveReturn() → 安裝 CTX handler → OSSemCreate → OSTaskCreate → OSStart → TaskStart（安裝 tick ISR）→ TaskStartCreateTasks

### Example 2 — Stack 監控、浮點、Mailbox

- Task3 刻意用大量區域變數（`char dummy[500]`）撐滿 stack → 示範 stack 使用量監控
- `OSTaskStkInit_FPE_x86()` 保留浮點空間
- Task4 和 Task5 透過 Mailbox 互傳字元訊息（Task4 發、Task5 收後 acknowledge）
- **重點**：ISR 會消耗被中斷任務的 stack；浮點操作需額外保留 stack 空間

### Example 3 — Message Queue 與 Hooks

- 使用 Message Queue 傳遞自定義資料結構（`TASK_USER_DATA`）
- `OSTaskSwHook` 在每次 context switch 時記錄各任務的執行時間
- Task1（sender）→ MsgQueue → Task2/3/4/5（receivers，功能相同）
- **重點**：Queue 能持有多則訊息（FIFO），適合一對多廣播場景；Hooks 是低成本的系統監控機制

### 本章總複習問題（Slide 51）

1. 如何撰寫一個 uC/OS-II 的骨架程式？
2. 各函式間的控制流怎麼流動？（main → OSStart → TaskStart → 應用任務）
3. 如何建立任務？
4. 如何用 Semaphore / Mailbox / Message Queue 同步任務？
5. Stack 空間如何配置與檢查？
6. 如何 hook 系統事件？
