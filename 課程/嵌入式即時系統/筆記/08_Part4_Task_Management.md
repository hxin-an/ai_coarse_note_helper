# 嵌入式即時系統 — uCOS Part 4 Task Management

> 來源：`uCOS Part 4 task management.pdf` | 產生日期：2026-03-24

## 前言

---

本份筆記整理 uC/OS-II Part 4 的任務管理 API 實作，涵蓋週期性與非週期性任務的結構差異、`OSTaskCreate()` 與 `OSTaskCreateExt()` 的建立程序、堆疊的記憶體配置與成長方向（`OS_STK_GROWTH`）、`OSTaskStkChk()` 堆疊使用量檢查機制、`OSTaskDel()` 的十步驟刪除程序、`OSTaskDelReq()` 安全請求刪除模式、`OSTaskChangePrio()` 的優先權變更程序，以及 `OSTaskSuspend()` / `OSTaskResume()` 的懸掛與恢復機制。本份內容建立在 Part 3 的 TCB 與就緒列表基礎上，深入展示核心資料結構的動態操作。

## 大綱

---

- 任務類型（Task Types）
  - 週期性任務（Periodic Task）
  - 非週期性任務（Aperiodic Task）
- 建立任務（Creating a Task）
  - `OSTaskCreate()` 實作解析
  - `OSTaskCreateExt()` 擴展版實作
  - 建立任務的注意事項
- 任務堆疊（Task Stacks）
  - 堆疊的記憶體配置
  - 堆疊成長方向（`OS_STK_GROWTH`）
  - 堆疊使用量檢查（`OSTaskStkChk()`）
- 刪除任務（Deleting a Task）
  - `OSTaskDel()` 程序
  - `OSTaskDelReq()` 安全刪除模式
- 變更任務優先權（Changing Task Priority）
  - `OSTaskChangePrio()` 程序
- 暫停與恢復任務（Suspending and Resuming）
  - `OSTaskSuspend()` 程序
  - `OSTaskResume()` 程序
  - 懸掛（Suspended）狀態的特殊性
- 查詢任務資訊（`OSTaskQuery()`）

---

## 任務類型（Task Types）

---

uC/OS-II 的任務分為兩種基本類型。

### 週期性任務（Periodic Task）

```c
void YourTask (void *pdata)
{
    for (;;) {
        /* USER CODE */
        /* 在每次迴圈結束時呼叫 blocking API，讓出 CPU 並等待下一個週期 */
        OSTimeDly(PERIOD);       /* 計時延遲，等待下一個週期 */
        OSSemPend(...);          /* 等待事件旗號 */
        OSMboxPend(...);         /* 等待信箱訊息 */
        OSQPend(...);            /* 等待佇列訊息 */
        OSTaskSuspend(OS_PRIO_SELF);  /* 自我懸掛，等待外部恢復 */
        /* USER CODE */
    }
}
```

- **無限迴圈**：週期性任務永遠循環執行，不可自行 return。
- **必須讓出 CPU**：每次迴圈必須呼叫至少一個 blocking API，否則低優先權任務永遠無法獲得 CPU。

### 非週期性任務（Aperiodic Task）

```c
void YourTask (void *pdata)
{
    /* USER CODE — 單次工作 */
    OSTaskDel(OS_PRIO_SELF);  /* 工作完成後刪除自身 */
}
```

- **按需建立**：非週期性任務在需要時由其他任務或 ISR 透過 `OSTaskCreate()` 動態建立。
- **自我刪除**：工作完成後呼叫 `OSTaskDel(OS_PRIO_SELF)` 刪除自身，釋放 TCB 與優先權。

---

## 建立任務（Creating a Task）

---

任務建立前，多工必須尚未啟動或至少已有一個任務就緒；不可在 ISR 中建立任務（可能造成死鎖）。

### `OSTaskCreate()` 實作解析

```c
INT8U OSTaskCreate (void (*task)(void *pd),  /* 任務函式指標 */
                    void *pdata,              /* 傳遞給任務的參數 */
                    OS_STK *ptos,             /* 堆疊頂端指標 */
                    INT8U prio)               /* 任務優先權 */
{
    OS_STK *psp;
    INT8U   err;

    OS_ENTER_CRITICAL();
    /* (1) 確認此優先權尚未被佔用 */
    if (OSTCBPrioTbl[prio] == (OS_TCB *)0) {
        OSTCBPrioTbl[prio] = (OS_TCB *)1;  /* 佔用優先權，立即重新啟用中斷 */
        OS_EXIT_CRITICAL();

        /* (2) 初始化任務堆疊（硬體相依，以組合語言實作） */
        /* 將任務入口位址壓入堆疊，使其看起來像剛被中斷 */
        psp = (OS_STK *)OSTaskStkInit(task, pdata, ptos, 0);

        /* (3) 初始化 TCB 並加入就緒列表 */
        err = OS_TCBInit(prio, psp, (OS_STK *)0, 0, (void *)0, 0);
        if (err == OS_NO_ERR) {
            OS_ENTER_CRITICAL();
            OSTCBCtr++;
            OS_EXIT_CRITICAL();
            if (OSRunning == TRUE) {
                OS_Sched();  /* 若多工已在執行，立即評估是否需要情境切換 */
            }
        } else {
            /* 初始化失敗，釋放優先權 */
            OS_ENTER_CRITICAL();
            OSTCBPrioTbl[prio] = (OS_TCB *)0;
            OS_EXIT_CRITICAL();
        }
        return (err);
    }
    OS_EXIT_CRITICAL();
    return (OS_PRIO_EXIST);  /* 優先權已被佔用 */
}
```

`OSTaskCreate()` 完成後，就緒列表、優先權表與 TCB 鏈結串列均已更新，任務即進入 Ready 狀態。

### `OSTaskCreateExt()` 擴展版實作

`OSTaskCreateExt()` 提供額外參數，支援堆疊使用量檢查、堆疊清零，以及使用者自訂 TCB 擴展：

| 參數 | 說明 |
|------|------|
| `task` | 任務函式指標 |
| `pdata` | 傳遞給任務的參數 |
| `ptos` | 堆疊頂端指標（Top of Stack） |
| `prio` | 任務優先權 |
| `id` | 任務識別碼（未來擴展用） |
| `pbos` | 堆疊底端指標（Bottom of Stack），用於堆疊檢查 |
| `stk_size` | 堆疊大小（元素數，每個元素 = `sizeof(OS_STK)` 位元組） |
| `pext` | 使用者自訂 TCB 擴展指標 |
| `opt` | 選項旗標（`OS_TASK_OPT_STK_CHK`、`OS_TASK_OPT_STK_CLR`、`OS_TASK_OPT_SAVE_FP`） |

- **堆疊清零（`OS_TASK_OPT_STK_CLR`）**：建立時以 `memset` 清零堆疊，為 `OSTaskStkChk()` 的檢查邏輯提供初始條件（清零後，未使用的堆疊區域保持為 0，`OSTaskStkChk()` 從 BOS 往上計算連續的 0 即可得到未使用大小）。

### 建立任務的注意事項

- **不可在 ISR 中建立任務**：`OS_Sched()` 在 `OSTaskCreate()` 結束時被呼叫，若在 ISR 中建立任務，排程器可能在 ISR 尚未結束時嘗試切換任務，造成死鎖。
- **多工啟動前至少需建立一個任務**：`OSStart()` 依賴就緒列表中有任務可執行。

---

## 任務堆疊（Task Stacks）

---

### 堆疊的記憶體配置

- **連續記憶體空間**：堆疊是一塊連續的記憶體，通常從全域陣列分配（靜態分配）。
- **元素大小**：由 `OS_STK` 巨集定義，在 x86 下為 16 bits（2 bytes）。

```c
OS_STK TaskStack[TASK_STACK_SIZE];  /* 靜態分配堆疊陣列 */
```

### 堆疊成長方向（`OS_STK_GROWTH`）

不同處理器的堆疊成長方向不同，uC/OS-II 以 `OS_STK_GROWTH` 巨集統一處理：

```c
#if OS_STK_GROWTH == 0
    /* 堆疊向高位址成長（由低到高） */
    /* TOS 的起始位址為陣列第一個元素 */
    OSTaskCreateExt(task, pdata, &TaskStack[0], prio, ...);
#else
    /* 堆疊向低位址成長（由高到低），x86 採用此方向 */
    /* TOS 的起始位址為陣列最後一個元素（最高位址） */
    OSTaskCreateExt(task, pdata, &TaskStack[TASK_STACK_SIZE-1], prio, ...);
#endif
```

- **x86 的堆疊方向**：向低位址成長（`OS_STK_GROWTH == 1`），因此傳入 `ptos` 時需指向陣列的最後一個元素（最高位址）。
- **BOS 與 TOS 的關係**：在 x86 下，BOS 在低位址（陣列起始），TOS 在高位址（陣列末端）；使用過的堆疊空間從 TOS 向 BOS 方向擴展。

### 堆疊使用量檢查（`OSTaskStkChk()`）

堆疊使用量檢查用於確認任務在最壞情況下（deepest worst-case）的實際堆疊使用深度，避免堆疊溢位。

使用步驟：

1. **在 `OS_CFG.H` 中設定 `OS_TASK_CREATE_EXT_EN = 1`**。
2. **以 `OSTaskCreateExt()` 建立任務**，並傳入 `OS_TASK_OPT_STK_CHK + OS_TASK_OPT_STK_CLR` 選項（清零堆疊是檢查的前提條件）。
3. **執行一段時間後呼叫 `OSTaskStkChk()`**，取得空閒與已使用的堆疊大小。

```c
INT8U OSTaskStkChk (INT8U prio, OS_STK_DATA *pdata)
{
    OS_STK  *pchk;
    INT32U   free = 0;
    INT32U   size;

    /* 取得目標任務的 TCB */
    ptcb = OSTCBPrioTbl[prio];
    size = ptcb->OSTCBStkSize;
    pchk = ptcb->OSTCBStkBottom;     /* 從 BOS 開始掃描 */

    /* 從 BOS 往 TOS 方向計算連續的 0（未使用的堆疊空間） */
#if OS_STK_GROWTH == 1
    while (*pchk++ == (OS_STK)0) { free++; }
#else
    while (*pchk-- == (OS_STK)0) { free++; }
#endif

    /* 回傳空閒與使用量（位元組） */
    pdata->OSFree = free * sizeof(OS_STK);
    pdata->OSUsed = (size - free) * sizeof(OS_STK);
    return (OS_NO_ERR);
}
```

- **原理**：由於建立時已清零，未曾被推入資料的堆疊區域保持為 0；從 BOS 起算，連續為 0 的區域即為空閒空間。
- **注意**：此函式僅給出歷史最深使用量，不代表目前正在使用的大小；必須在系統執行足夠長時間後才有代表性。

---

## 刪除任務（Deleting a Task）

---

**任務刪除（Task Deletion）**釋放任務相關的所有資料結構：TCB 歸還自由列表、優先權表清除、就緒列表或等待列表中的 bit 清除。

### `OSTaskDel()` 程序

`OSTaskDel()` 的執行步驟如下：

1. **禁止刪除閒置任務**：閒置任務（priority 63）不可被刪除。
2. **禁止在 ISR 中刪除任務**：`OSTaskDel()` 結束時會呼叫 `OS_Sched()`，ISR 中不可觸發排程。
3. **確認目標任務存在**：查詢優先權表確認任務確實存在。
4. **從 TCB 鏈結串列移除**：更新雙向鏈結的 `OSTCBNext` / `OSTCBPrev`。
5. **從就緒列表移除**（若任務在就緒狀態）：清除 `OSRdyTbl` 與 `OSRdyGrp` 的對應 bit。
6. **從事件等待列表移除**（若任務正在等待事件）：清除事件控制區塊（ECB）中的對應 bit。
7. **從旗標節點移除**（若任務在等待旗標）：呼叫 `OS_FlagUnlink()`。
8. **處理自我刪除時的特殊情況**：若任務刪除自身，需透過 `OS_Dummy()` 讓目前的 ISR 有機會完成，避免提前觸發排程。
9. **呼叫 `OSTaskDelHook()`**：使用者可自訂的 hook，用於釋放應用程式層的資源。
10. **釋放 TCB**：TCB 歸還給 `OSTCBFreeList`，優先權表清除，呼叫 `OS_Sched()`。

```c
INT8U OSTaskDel (INT8U prio)
{
    OS_EVENT     *pevent;
    OS_FLAG_NODE *pnode;
    OS_TCB       *ptcb;
    BOOLEAN       self;

    if (OSIntNesting > 0) {             /* 禁止在 ISR 中刪除任務 */
        return (OS_TASK_DEL_ISR);
    }
    /* ... 各步驟的實作省略，見原始碼 ... */
    OSTCBFreeList = ptcb;               /* TCB 歸還自由列表 */
    OS_EXIT_CRITICAL();
    OS_Sched();                         /* 觸發排程 */
    return (OS_NO_ERR);
}
```

### `OSTaskDelReq()` 安全刪除模式

直接以 `OSTaskDel()` 刪除其他任務（非自身）是危險的，因為被刪除的任務可能持有旗號或動態記憶體尚未釋放。**安全做法**是向目標任務發送刪除請求，由目標任務在適當時機自行釋放資源後刪除自身。

```c
/* 請求者任務（Requestor Task） */
void RequestorTask (void *pdata)
{
    for (;;) {
        if (/* 需要刪除 TaskToBeDeleted */) {
            /* 持續發送刪除請求，直到目標任務已刪除 */
            while (OSTaskDelReq(TASK_TO_DEL_PRIO) != OS_TASK_NOT_EXIST) {
                OSTimeDly(1);
            }
        }
    }
}

/* 目標任務（TaskToBeDeleted） */
void TaskToBeDeleted (void *pdata)
{
    while (1) {
        /* 定期檢查是否有刪除請求 */
        if (OSTaskDelReq(OS_PRIO_SELF) == OS_TASK_DEL_REQ) {
            /* 釋放所有持有的資源（旗號、動態記憶體等） */
            /* ... 釋放資源 ... */
            OSTaskDel(OS_PRIO_SELF);  /* 安全地自我刪除 */
        } else {
            /* 繼續執行 */
        }
    }
}
```

- **`OSTaskDelReq(TASK_PRIO)`**：設定目標任務 TCB 的 `OSTCBDelReq` 旗標為刪除請求。
- **`OSTaskDelReq(OS_PRIO_SELF)`**：任務查詢自身的 `OSTCBDelReq`，若為請求則執行資源釋放與自我刪除。

---

## 變更任務優先權（Changing Task Priority）

---

`OSTaskChangePrio(oldPrio, newPrio)` 允許在執行期間動態調整任務優先權，但不可變更閒置任務的優先權。

### `OSTaskChangePrio()` 程序

1. **佔用新優先權**：`OSTCBPrioTbl[newPrio] = (OS_TCB *)1`，確保新優先權未被其他任務使用。
2. **更新優先權表**：從舊優先權位置移除，插入新優先權位置（`OSTCBPrioTbl[newPrio] = ptcb`，`OSTCBPrioTbl[oldPrio] = NULL`）。
3. **調整就緒列表**（若任務處於就緒狀態）：移除舊優先權的 bit，設定新優先權的 bit。
4. **調整事件等待列表**（若任務正在等待事件）：在 ECB 的 `OSEventTbl` 中移除舊優先權 bit，設定新優先權 bit。
5. **更新 TCB**：修改 `OSTCBPrio`、`OSTCBX`、`OSTCBY`、`OSTCBBitX`、`OSTCBBitY` 欄位（這些是預先計算的就緒列表索引）。
6. **呼叫 `OS_Sched()`**：重新評估排程，確保最高優先權就緒任務取得 CPU。

---

## 暫停與恢復任務（Suspending and Resuming）

---

### 懸掛（Suspended）狀態的特殊性

- **獨立於等待（Waiting）狀態**：懸掛（suspended）是一個獨立的狀態旗標（`OS_STAT_SUSPEND`），可以疊加在 Waiting 狀態之上。一個任務可以同時處於「等待旗號 + 被懸掛」的複合狀態。
- **恢復方式唯一**：懸掛狀態只能由 `OSTaskResume()` 解除，計時到期或事件發生無法恢復懸掛的任務。
- **持有旗號時懸掛的危險**：若任務持有旗號或互斥鎖時被懸掛，其他等待同一資源的任務將永遠無法繼續，造成死鎖。

### `OSTaskSuspend()` 程序

1. **檢查輸入優先權**：不可懸掛閒置任務（priority 63）。
2. **從就緒列表移除**：清除 `OSRdyTbl` 與 `OSRdyGrp` 中的對應 bit。
3. **設定懸掛旗標**：在 `OSTCBStat` 中設定 `OS_STAT_SUSPEND` bit。
4. **若為自我懸掛，呼叫 `OS_Sched()`**：讓排程器選擇下一個就緒任務執行。

```c
INT8U OSTaskSuspend (INT8U prio)
{
    BOOLEAN  self;
    OS_TCB  *ptcb;

    OS_ENTER_CRITICAL();
    self = (prio == OS_PRIO_SELF) ? TRUE : FALSE;
    ptcb = OSTCBPrioTbl[prio];
    /* 從就緒列表移除 */
    if ((OSRdyTbl[ptcb->OSTCBY] &= ~ptcb->OSTCBBitX) == 0)
        OSRdyGrp &= ~ptcb->OSTCBBitY;
    /* 設定懸掛旗標 */
    ptcb->OSTCBStat |= OS_STAT_SUSPEND;
    OS_EXIT_CRITICAL();
    if (self) {
        OS_Sched();  /* 若為自我懸掛，觸發排程切換至其他任務 */
    }
    return (OS_NO_ERR);
}
```

### `OSTaskResume()` 程序

1. **檢查輸入優先權**：確認目標任務確實處於懸掛狀態。
2. **清除懸掛旗標**：在 `OSTCBStat` 中清除 `OS_STAT_SUSPEND` bit。
3. **若任務同時不在等待任何事件，加回就緒列表**：若任務同時處於「等待 + 懸掛」的複合狀態，清除懸掛旗標後任務仍留在等待狀態，不可立即加入就緒列表。
4. **呼叫 `OS_Sched()`**：重新評估排程。

```c
INT8U OSTaskResume (INT8U prio)
{
    OS_TCB *ptcb;

    OS_ENTER_CRITICAL();
    ptcb = OSTCBPrioTbl[prio];
    /* 清除懸掛旗標 */
    ptcb->OSTCBStat &= ~OS_STAT_SUSPEND;
    /* 若任務不再等待任何其他事件，加回就緒列表 */
    if (ptcb->OSTCBStat == OS_STAT_RDY) {
        OSRdyGrp             |= ptcb->OSTCBBitY;
        OSRdyTbl[ptcb->OSTCBY] |= ptcb->OSTCBBitX;
        OS_EXIT_CRITICAL();
        OS_Sched();
    } else {
        OS_EXIT_CRITICAL();
    }
    return (OS_NO_ERR);
}
```

---

## 查詢任務資訊（`OSTaskQuery()`）

---

`OSTaskQuery()` 回傳目標任務 TCB 的完整複本，供使用者程式碼查閱任務當前狀態。

```c
INT8U OSTaskQuery (INT8U prio, OS_TCB *pdata)
{
    OS_TCB *ptcb;

    OS_ENTER_CRITICAL();
    ptcb = OSTCBPrioTbl[prio];
    if (ptcb == (OS_TCB *)0) {
        OS_EXIT_CRITICAL();
        return (OS_PRIO_EXIST);
    }
    *pdata = *ptcb;  /* 複製整個 TCB 至使用者提供的緩衝區 */
    OS_EXIT_CRITICAL();
    return (OS_NO_ERR);
}
```

- **唯讀使用**：取得的 TCB 複本僅供查閱，不可修改 `OSTCBNext`、`OSTCBPrev` 等鏈結欄位，否則會破壞核心資料結構。
- **快照語義**：回傳的是呼叫當下的瞬間快照，後續 TCB 狀態變化不會反映在複本中。

---

**備註：本筆記整理 uC/OS-II Part 4 的任務管理 API 實作，關鍵貢獻在於以 OSTaskCreate/Ext 建立程序、OSTaskStkChk 堆疊檢查機制、OSTaskDel 十步驟刪除程序、OSTaskDelReq 安全刪除模式，以及 OSTaskSuspend/Resume 的複合狀態設計，完整呈現核心如何透過操作 TCB、就緒列表與優先權表實現任務的全生命週期管理。**
