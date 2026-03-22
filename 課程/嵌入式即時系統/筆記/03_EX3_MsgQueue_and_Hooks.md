# 嵌入式即時系統 — uC/OS-II EX3 深度解析：消息隊列、OSTCBExtPtr 與 Hooks 實戰
> 來源：`EX3_x86L\BC45\SOURCE\TEST.C` | 產生日期：2026-03-21

## 前言
---

EX3 是四個範例中程式碼最複雜、但也最接近真實 RTOS 專案的一個。它在 EX2 的基礎上同時示範三件新事物：**消息隊列（Message Queue）**——Mailbox 的多容量升級版；**`OSTCBExtPtr`**——讓每個任務攜帶自訂資料，讓 OS「認識你」；以及 **Hooks**——讓你的程式碼在 OS 內部事件發生時自動被呼叫，實現低成本的效能監控。

## 大綱
---

- [執行環境與步驟](#執行環境與步驟)
- [這個範例在測試什麼？](#這個範例在測試什麼)
- [main() — 與 EX2 的差異](#main--與-ex2-的差異)
- [消息隊列（Message Queue）— Mailbox 的進化版](#消息隊列message-queue--mailbox-的進化版)
- [`OSTCBExtPtr` — 幫任務掛名牌](#ostcbextptr--幫任務掛名牌)
- [Hooks 實戰](#hooks-實戰)
  - [`OSTaskSwHook()` — 任務切換時被呼叫](#ostaskswHook--任務切換時被呼叫)
  - [`OSTaskStatHook()` — 統計任務週期性被呼叫](#ostaskstathook--統計任務週期性被呼叫)
- [計時系統的完整運作流程](#計時系統的完整運作流程)
- [總結：EX3 新增了什麼？](#總結ex3-新增了什麼)

## 執行環境與步驟
---

EX3 同樣需要在 DOSBox 下執行：

```
mount c <uCOS-II 資料夾的絕對路徑>
cd c:\SOFTWARE\uCOS-II\EX3_x86L\BC45\test
maketest.bat
test.exe
```

執行後會看到一張任務效能報表，顯示每個任務的名稱、執行次數、單次執行時間（μs）、累積執行時間，以及佔總 CPU 時間的百分比。

## 這個範例在測試什麼？
---

EX3 的螢幕顯示了一張「任務效能報表」，包含：每個任務執行了幾次、每次花多少微秒、總執行時間佔整體的百分比。

| 任務 | 職責 | 關鍵行為 |
| :--- | :--- | :--- |
| `TaskStart` | 系統初始化、每秒更新主顯示 | 建立 `MsgQueue` |
| `TaskClk` | 顯示時間 | 每 500ms 更新 |
| `Task1` | **消息隊列接收者** | 從 Queue 等待訊息並顯示 |
| `Task2` | 發送者 #1 | 每 500ms 塞一個 `"Task 2"` 字串進 Queue |
| `Task3` | 發送者 #2 | 每 500ms 塞一個 `"Task 3"` 字串進 Queue |
| `Task4` | 發送者 #3 | 每 500ms 塞一個 `"Task 4"` 字串進 Queue |
| `Task5` | 時間填充任務 | 每 100ms delay 一次（讓統計更有意義） |

## main() — 與 EX2 的差異
---

EX3 的 `main()` 比 EX2 簡單，但有三個關鍵變化：

**1. 拿掉了 FPU 前處理**

EX2 在建立 TaskStart 之前有三行 `OSTaskStkInit_FPE_x86` 的前處理，在 Stack 頂端保留 94 bytes 給 FPU 快照。EX3 完全移除這段——TaskStart 不再做浮點運算，不需要 FPU 保護。

**2. 選項 flag 從 `STK_CHK | STK_CLR` 改成 `0`**

EX2 每個任務都開啟 `OS_TASK_OPT_STK_CHK | OS_TASK_OPT_STK_CLR`，讓 `OSTaskStkChk()` 能量測 Stack 使用量。EX3 傳 `0`——Stack 監控功能整個關掉，儀錶板改為顯示 CPU 時間統計。

**3. 參數 8（`OSTCBExtPtr`）第一次真正被使用**

```c
// EX2：傳 NULL，掛名牌的欄位空著
OSTaskCreateExt(TaskStart, ..., (void *)0, 0);

// EX3：先填名稱，再把結構體指標掛上去
strcpy(TaskUserData[TASK_START_ID].TaskName, "StartTask");
OSTaskCreateExt(TaskStart, ..., &TaskUserData[TASK_START_ID], 0);
```

這三個變化合在一起說明了 EX3 的設計方向：**放棄 Stack 監控，改做 CPU 時間效能分析**，而 `OSTCBExtPtr` 就是串起這一切的關鍵——Hook 函數透過它把時間資料寫回每個任務自己的統計結構。

## 消息隊列（Message Queue）— Mailbox 的進化版
---

### 根本差異：一格 vs 多格

**Mailbox** 像是「一格的信箱」：裡面只能放一個訊息，你放進去之前必須確認前一個已被取走。
**Message Queue** 像是「有容量的待辦清單」：可以一次堆疊多個訊息，接收方照順序取走。

```c
// 宣告：一個 Queue 物件 + 一塊儲存訊息指標的陣列
OS_EVENT *MsgQueue;
void     *MsgQueueTbl[20];     // ★ 最多存 20 個訊息的指標

// 建立：在 TaskStart 裡呼叫
MsgQueue = OSQCreate(&MsgQueueTbl[0], MSG_QUEUE_SIZE);
//                   ^ 陣列起始位址    ^ 最大容量 = 20
```

### 三個關鍵 API

| 函數 | 角色 | 說明 |
| :--- | :--- | :--- |
| `OSQCreate(tbl, size)` | 建立者 | 建立 Queue，提供底層陣列 |
| `OSQPost(q, msg)` | 發送者 | 把訊息指標加入 Queue 尾端；若滿則回傳錯誤 |
| `OSQPend(q, timeout, &err)` | 接收者 | 從 Queue 頭端取一個訊息；若空則 Block 等待 |

### EX3 的多對一通訊模式

Task2、Task3、Task4 都不斷往同一個 Queue 推訊息，Task1 是唯一的接收者：

```c
// Task2、Task3、Task4 各自做同一件事——每 500ms 把自己的名字推進 Queue
void  Task2 (void *pdata) {
    char msg[20];
    strcpy(&msg[0], "Task 2");
    for (;;) {
        OSQPost(MsgQueue, (void *)&msg[0]);  // 推入 Queue
        OSTimeDlyHMSM(0, 0, 0, 500);
    }
}

// Task1 是唯一的接收者，不管誰送來的它都接
void  Task1 (void *pdata) {
    char *msg;
    INT8U err;
    for (;;) {
        msg = (char *)OSQPend(MsgQueue, 0, &err); // 等待任何一個訊息
        PC_DispStr(70, 13, msg, ...);              // 顯示（會看到 Task 2/3/4 輪流出現）
        OSTimeDlyHMSM(0, 0, 0, 100);
    }
}
```

三個發送者以 500ms 為週期輪流推訊息，Task1 每次取一個並等 100ms。由於 Queue 有 20 格緩衝，即使 Task1 偶爾慢一點，訊息也不會直接丟失。

**Task5 的特殊角色**：Task5 的程式碼只有一個 100ms delay，沒有任何業務邏輯。它存在的唯一目的是讓統計數字更豐富——多一個任務就多一列資料、多一筆切換紀錄，讓 `OSTaskStatHook()` 的百分比表格看起來更有說服力。這是教學範例常見的「填充任務」設計。

## `OSTCBExtPtr` — 幫任務掛名牌
---

### 什麼是 TCB？

每個任務在 OS 內部有一個對應的 **Task Control Block（TCB）**，類型是 `OS_TCB`。可以把它想成任務的「戶口名簿」，記錄任務的優先權、Stack 指標、狀態等。

### `OSTCBExtPtr` 是什麼？

`OS_TCB` 結構體裡有一個欄位 `OSTCBExtPtr`，原本是 `void *`（空指標，預設為 NULL）。它就像是名簿上留的「備注欄」，讓你把任何自訂資料接上去。

### EX3 的用法

**第一步：定義自訂資料結構**

```c
typedef struct {
    char    TaskName[30];       // 任務名稱字串
    INT16U  TaskCtr;            // 此任務被執行了幾次
    INT16U  TaskExecTime;       // 上一次執行花了多少微秒
    INT32U  TaskTotExecTime;    // 總執行時間（微秒）
} TASK_USER_DATA;

TASK_USER_DATA  TaskUserData[7];  // 每個任務各一筆
```

**第二步：建立任務時，把結構體指標傳入**

```c
strcpy(TaskUserData[TASK_1_ID].TaskName, "MsgQ Rx Task");

OSTaskCreateExt(Task1,
                (void *)0,
                &Task1Stk[TASK_STK_SIZE - 1],
                TASK_1_PRIO,
                TASK_1_ID,
                &Task1Stk[0],
                TASK_STK_SIZE,
                &TaskUserData[TASK_1_ID],  // ★ 這就是 OSTCBExtPtr 的值
                0);
```

**第三步：在 Hook 裡取用**

```c
puser = OSTCBCur->OSTCBExtPtr;  // 取得當前任務的自訂資料
puser->TaskCtr++;               // 操作
```

## Hooks 實戰
---

**Hook（鉤子）** 是 uC/OS-II 在特定系統事件發生時，會自動呼叫的函數。你只要在 `TEST.C` 裡定義這些函數，OS 就會在正確時機呼叫它們。

重要前提：
*   Hook 必須在 `OS_CFG.H` 中開啟對應的開關（例如 `OS_CPU_HOOKS_EN`）。
*   Hook 是**編譯期決定**的，沒有「執行期動態註冊」功能。

### `OSTaskSwHook()` — 任務切換時被呼叫

這是 EX3 最核心的 Hook。每次 OS 從一個任務切換到另一個任務，這個函數就會被呼叫一次：

```c
void  OSTaskSwHook (void)
{
    INT16U           time;
    TASK_USER_DATA  *puser;

    time  = PC_ElapsedStop();    // ★ 停止為「被切換出去的任務」計時
    PC_ElapsedStart();           // ★ 開始為「下一個即將執行的任務」計時

    puser = OSTCBCur->OSTCBExtPtr;  // 取得「被切換出去的任務」的自訂資料
    if (puser != (TASK_USER_DATA *)0) {
        puser->TaskCtr++;                        // 執行次數 +1
        puser->TaskExecTime     = time;          // 記錄這次執行時間
        puser->TaskTotExecTime += time;          // 累加總執行時間
    }
}
```

> **重點**：`OSTCBCur` 在 `OSTaskSwHook` 被呼叫的瞬間，指向的是**「正要被切換走的任務」**，也就是剛執行完的那個任務。所以這裡才能正確地把時間記到它身上。

### `OSTaskStatHook()` — 統計任務週期性被呼叫

uC/OS-II 的統計任務大約每秒呼叫一次 `OSTaskStatHook()`：

```c
void  OSTaskStatHook (void)
{
    INT32U total = 0L;

    // 第一輪：把所有任務的總執行時間加總，並顯示到螢幕
    for (i = 0; i < 7; i++) {
        total += TaskUserData[i].TaskTotExecTime;
        DispTaskStat(i);
    }

    // 第二輪：計算每個任務佔總時間的百分比
    if (total > 0) {
        for (i = 0; i < 7; i++) {
            pct = 100 * TaskUserData[i].TaskTotExecTime / total;
            sprintf(s, "%3d %%", pct);
            PC_DispStr(62, i + 11, s, ...);
        }
    }

    // 防止溢位：若累計超過 10 億，歸零重算
    if (total > 1000000000L) {
        for (i = 0; i < 7; i++) {
            TaskUserData[i].TaskTotExecTime = 0L;
        }
    }
}
```

### 其他定義但沒有實際邏輯的 Hooks（空函數）

```c
void  OSInitHookBegin  (void) {}               // OSInit() 開始時
void  OSInitHookEnd    (void) {}               // OSInit() 結束時
void  OSTaskCreateHook (OS_TCB *ptcb) { ptcb = ptcb; }  // 任務被建立時
void  OSTaskDelHook    (OS_TCB *ptcb) { ptcb = ptcb; }  // 任務被刪除時
void  OSTaskIdleHook   (void) {}               // Idle 任務執行時
void  OSTCBInitHook    (OS_TCB *ptcb) { ptcb = ptcb; }  // TCB 初始化時
void  OSTimeTickHook   (void) {}               // 每個 Tick 中斷發生時
```

> 為什麼要定義空函數？因為在 `OS_CFG.H` 中開啟 Hooks 後，OS 的核心程式碼會呼叫這些函數名稱。如果你不定義，連結器會報「找不到函數」的錯誤。空函數是「我知道你叫我，但我什麼都不做」的表態。

## 計時系統的完整運作流程
---

EX3 的計時依賴兩個函數：
*   `PC_ElapsedStart()` — 記錄當前時間戳
*   `PC_ElapsedStop()` — 計算從上次 Start 到現在的時間差（微秒）

完整流程：
1. **程式啟動時**，`PC_ElapsedInit()` 初始化計時器硬體（讀取 x86 的 8254 Timer）。
2. **`OSStart()` 啟動 TaskStart 前**，`OSTaskSwHook()` 第一次被呼叫，執行 `PC_ElapsedStart()`，為 TaskStart 開始計時。
3. **每次任務切換**，`OSTaskSwHook()` 先停止計時（Stop → 記錄時間到目前任務），再重新開始（Start → 為下一個任務計時）。
4. **每秒 `OSTaskStatHook()` 被呼叫一次**，統計所有任務的執行時間，計算百分比並顯示。

## 總結：EX3 新增了什麼？
---

| 主題 | EX2 | EX3 |
| :--- | :---: | :---: |
| IPC 機制 | Mailbox（1 對 1） | Message Queue（多對 1） |
| 任務自訂資料 | ❌ | ✅ `OSTCBExtPtr` |
| Hooks | 未使用 | ✅ `OSTaskSwHook`, `OSTaskStatHook` 等 |
| 效能分析 | Stack 使用量 | ✅ CPU 時間百分比、每次執行時間 |
| 通訊模式 | 握手（A→B→A） | 多發送 → 單接收（Queue 緩衝） |
