# 嵌入式即時系統 — uC/OS-II EX2 深度解析：郵件箱通訊與 Stack 健康監控
> 來源：`EX2_x86L\BC45\SOURCE\TEST.C` | 產生日期：2026-03-21

## 前言
---

如果說 EX1 告訴你「多個任務如何共享資源（Semaphore）」，那 EX2 告訴你的就是「任務之間如何互相傳訊息（Mailbox）」，以及「如何在執行期間監控一個任務到底用掉了多少 Stack」。EX2 同時引入了 `OSTaskCreateExt`——比 EX1 的 `OSTaskCreate` 更完整的任務建立 API，讓 OS 掌握更多關於任務的資訊，進而支援 Stack 監控與浮點暫存器保留等進階功能。

## 大綱
---

- [執行環境與步驟](#執行環境與步驟)
- [這個範例在測試什麼？](#這個範例在測試什麼)
- [main() 與 TaskStart() 完整流程解析](#main-與-taskstart-完整流程解析)
- [`OSTaskCreate` vs `OSTaskCreateExt`](#ostaskcreate-vs-ostaskcreateext)
- [Stack 健康監控 — `OSTaskStkChk()`](#stack-健康監控--ostaskstkchk)
- [Task3 的「故意搞壞」設計](#task3-的故意搞壞設計)
- [郵件箱通訊（Mailbox）— Task4 ↔ Task5](#郵件箱通訊mailbox--task4--task5)
- [浮點數空間預留 — `OSTaskStkInit_FPE_x86`](#浮點數空間預留--ostaskstkInit_fpe_x86)
- [總結：EX2 新增了什麼？](#總結ex2-新增了什麼)

## 執行環境與步驟
---

EX2 同樣跑在 **DOSBox** 下（16-bit DOS 環境），編譯工具是 **Borland C++ 4.5**。

```bat
# 1. 在 DOSBox 中掛載專案資料夾
mount c D:\SOFTWARE\uCOS-II

# 2. 切換到 EX2 的編譯目錄
cd c:\EX2_x86L\BC45\test

# 3. 執行編譯腳本（產生 TEST.EXE）
maketest.bat

# 4. 執行程式
test.exe
```

執行後你會看到一個儀錶板，左邊顯示各任務的 Stack 使用統計（Total / Free / Used），右側有旋轉轉輪與 Mailbox 字母傳遞的動態畫面。按 **ESC** 結束，回到 DOS prompt。

> DOSBox 的用途：EX2 使用 x86 16-bit 組語（`OS_CPU_A.ASM`）與 Borland C++ 4.5 編譯，無法在現代 64-bit Windows 上直接執行。DOSBox 模擬 DOS 環境與 x86 實模式，讓舊程式碼可以正確執行。

## 這個範例在測試什麼？
---

執行 EX2 後，你會看到一個儀錶板畫面，顯示每個任務的 Stack 使用狀況與執行時間。這個範例包含 **7 個任務**，每個任務各自負責一件事：

| 任務 | 優先權 | 職責 |
| :--- | :---: | :--- |
| `TaskStart` | 10 | 系統初始化，主控顯示 |
| `TaskClk` | 11 | 在螢幕右下角顯示當前時間 |
| `Task1` | 12 | **每 100ms 量測所有任務的 Stack 使用狀況** |
| `Task2` | 13 | 在螢幕上顯示順時針旋轉的轉輪 `| / - \` |
| `Task3` | 14 | 顯示逆時針旋轉的轉輪，**且刻意塞滿 500 bytes stack** |
| `Task4` | 15 | 把字母 A→Z 依序傳給 Task5（透過 Mailbox） |
| `Task5` | 16 | 接收 Task4 的字母，顯示後回傳確認訊號 |

這個範例的設計意圖：**讓你親眼看到不同任務的 Stack「吃了多少」，以及 Mailbox 如何讓兩個任務同步溝通。**

## main() 與 TaskStart() 完整流程解析
---

EX2 的 `main()` 和 `TaskStart()` 與 EX1 相比多了幾個關鍵步驟，每一個都對應一個新功能。

### main() — 和 EX1 的差異

```c
void main (void)
{
    OS_STK *ptos;
    OS_STK *pbos;
    INT32U  size;

    PC_DispClrScr(DISP_FGND_WHITE);
    OSInit();
    PC_DOSSaveReturn();
    PC_VectSet(uCOS, OSCtxSw);

    PC_ElapsedInit();                          // ★ EX2 新增

    ptos = &TaskStartStk[TASK_STK_SIZE - 1];  // ★ EX2 新增：FPU 前處理
    pbos = &TaskStartStk[0];
    size = TASK_STK_SIZE;
    OSTaskStkInit_FPE_x86(&ptos, &pbos, &size);

    OSTaskCreateExt(TaskStart, ..., ptos, ..., pbos, size,  // ★ 改用 Ext 版本
                    OS_TASK_OPT_STK_CHK | OS_TASK_OPT_STK_CLR);

    OSStart();
}
```

EX2 新增的部分：

- **`PC_ElapsedInit()`**：初始化 8253 計時器的第 2 個通道，用來量測微秒級的執行時間。Task1 會用 `PC_ElapsedStart()` / `PC_ElapsedStop()` 來計算 `OSTaskStkChk()` 本身花了多少微秒，並顯示在儀錶板的 ExecTime 欄位。EX1 沒有這個，因為 EX1 不需要計時。
- **FPU 前處理三行**：x86 的 FPU 有一組獨立暫存器（ST0～ST7），Context Switch 預設不儲存它們，會導致浮點計算被其他任務汙染。`OSTaskStkInit_FPE_x86()` 的作用是在 Stack 頂端預留一塊空間，讓 Context Switch 有地方存放 FPU 快照。它把 `ptos` 往下移、`size` 縮小，再把修正後的值交給 `OSTaskCreateExt`。詳細原理見[浮點數空間預留](#浮點數空間預留--ostaskstkInit_fpe_x86)章節。
- **`OSTaskCreateExt` 取代 `OSTaskCreate`**：多傳入 `pbos`、`size`、Task ID 和選項 flag，OS 才能追蹤 Stack 邊界，讓 `OSTaskStkChk()` 得以運作。

### TaskStart() — 和 EX1 的差異

```c
void TaskStart (void *pdata)
{
    TaskStartDispInit();              // 畫出儀錶板框架

    OS_ENTER_CRITICAL();
    PC_VectSet(0x08, OSTickISR);      // 安裝 Tick ISR（與 EX1 相同）
    PC_SetTickRate(OS_TICKS_PER_SEC);
    OS_EXIT_CRITICAL();

    OSStatInit();                     // ★ EX2 新增：啟動統計任務

    AckMbox = OSMboxCreate((void *)0); // ★ EX2 新增：建立兩個 Mailbox
    TxMbox  = OSMboxCreate((void *)0);

    TaskStartCreateTasks();           // ★ EX2 新增：獨立的任務建立函數

    for (;;) {
        TaskStartDisp();              // 每秒更新儀錶板數字
        if (PC_GetKey(&key) && key == 0x1B) { PC_DOSReturn(); }
        OSCtxSwCtr = 0;               // ★ EX2 新增：重置 Context Switch 計數器
        OSTimeDly(OS_TICKS_PER_SEC);
    }
}
```

新增內容說明：

- **`OSStatInit()`**：啟動 uC/OS-II 內建的統計任務（Statistics Task），讓 OS 開始追蹤 CPU 使用率（`OSCPUUsage`）和執行中任務數（`OSTaskCtr`）。呼叫這個函數後，儀錶板底部的「CPU Usage」和「#Tasks」欄位才有數字可顯示。
- **`OSMboxCreate()`**：在這裡建立 `AckMbox` 和 `TxMbox` 兩個信箱，讓 Task4 和 Task5 後續可以使用。必須在 `TaskStartCreateTasks()` 之前建立，因為 Task4/5 一啟動就會去 Pend 這兩個信箱。
- **`TaskStartCreateTasks()`**：EX2 把所有其他任務的建立抽出來放到一個獨立函數，讓 `TaskStart` 的主迴圈更乾淨。這是程式架構上的整理，功能與 EX1 在 `TaskStart` 裡直接建立任務相同。
- **`OSCtxSwCtr = 0`**：`OSCtxSwCtr` 是 OS 全域計數器，每次 Context Switch 就加 1。`TaskStart` 每秒讀一次數值顯示到儀錶板，然後清零，等於每秒統計一次「每秒發生幾次任務切換」。

### `_8087` — FPU 型別偵測

`TaskStartDisp()` 還多了一段偵測 FPU 型別的程式碼：

```c
switch (_8087) {   // Borland C++ 的全域變數，開機時自動偵測 FPU
    case 0: "NO  FPU"   break;
    case 1: "8087 FPU"  break;
    case 2: "80287 FPU" break;
    case 3: "80387 FPU" break;
}
```

`_8087` 是 Borland C++ 的特殊全域變數，編譯器啟動時會自動偵測系統是否有 FPU 晶片並寫入這個值。儀錶板右下角會顯示目前使用的 FPU 型號，讓你確認浮點保護是否有意義（如果沒有 FPU，`OSTaskStkInit_FPE_x86` 保留的空間就浪費了）。

## `OSTaskCreate` vs `OSTaskCreateExt`
---

EX1 用的是 `OSTaskCreate`。EX2 改用了更強大的 **`OSTaskCreateExt`**。

`OSTaskCreate` 是「給我一個任務，我幫你跑」，而 `OSTaskCreateExt` 是「給我一個任務，我幫你跑，**同時告訴我堆疊的底部在哪、堆疊有多大、有沒有什麼特殊選項**」。

```c
// EX1 的寫法（簡易版）
OSTaskCreate(Task,                        // 函數指標：這個任務要執行什麼
             (void *)data,                // 傳入參數
             &Stk[STK_SIZE - 1],          // Stack 頂端（高地址）
             prio);                       // 優先權

// EX2 的寫法（完整版）
OSTaskCreateExt(Task,                     // 函數指標
                (void *)0,                // 傳入參數
                &TaskStk[STK_SIZE - 1],   // ★ Stack 頂端（TOS）
                TASK_PRIO,                // 優先權
                TASK_ID,                  // ★ 任務 ID（用於 Stack 檢查索引）
                &TaskStk[0],              // ★ Stack 底部（BOS，低地址）
                TASK_STK_SIZE,            // ★ Stack 大小（單位：word）
                (void *)0,                // ★ 額外使用者資料指標（EX3 才用到）
                OS_TASK_OPT_STK_CHK | OS_TASK_OPT_STK_CLR); // ★ 選項 flag
```

### 關鍵：`OS_TASK_OPT_STK_CHK | OS_TASK_OPT_STK_CLR`

這兩個 flag 是 Stack 監控功能的開關：

| Flag | 作用 |
| :--- | :--- |
| `OS_TASK_OPT_STK_CLR` | 建立任務時，先把整個 Stack 記憶體**歸零（填 0x00）**。這是 Stack 檢查的前提條件，因為 `OSTaskStkChk()` 是靠「從底部往上數，有幾個 word 還是 0」來估算 Free space。 |
| `OS_TASK_OPT_STK_CHK` | 告訴 OS 這個任務允許被 `OSTaskStkChk()` 檢查。 |

> 如果只加 `STK_CHK` 而不加 `STK_CLR`，Stack 初始值是隨機的，`OSTaskStkChk()` 無法區分哪些位置是「真的被用過」，量測結果會不準確。

## Stack 健康監控 — `OSTaskStkChk()`
---

`Task1` 是這個範例的「Stack 健診醫生」，每 100ms 幫所有任務量一次 Stack：

```c
void  Task1 (void *pdata)
{
    OS_STK_DATA data;   // 存放量測結果的結構體
    INT16U      time;   // 執行時間（微秒）
    INT8U       i;

    for (;;) {
        for (i = 0; i < 7; i++) {
            PC_ElapsedStart();                           // 開始為 StkChk 本身計時
            err = OSTaskStkChk(TASK_START_PRIO + i, &data); // 對第 i 個任務量測
            time = PC_ElapsedStop();                     // 停止計時，取得微秒數

            sprintf(s, "%4ld  %4ld  %4ld  %6d",
                    data.OSFree + data.OSUsed, // Total Stack（Free + Used）
                    data.OSFree,               // 未使用的 Stack（從 BOS 往上的零空間）
                    data.OSUsed,               // 已使用的 Stack（非 0 的區域）
                    time);                     // OSTaskStkChk() 本身花了幾微秒
            PC_DispStr(19, 12 + i, s, ...);
        }
        OSTimeDlyHMSM(0, 0, 0, 100);                    // 每 100ms 做一次
    }
}
```

### `OS_STK_DATA` 的量測原理

| 欄位 | 意義 |
| :--- | :--- |
| `OSFree` | Stack 中還沒被碰過的 word 數量（全 0 的區域） |
| `OSUsed` | Stack 中已被寫入過的 word 數量（非 0 的區域） |

uC/OS-II 的 Stack 由高地址往低地址成長，也就是任務剛建立時 Stack 指標在高地址（TOS），每次 push 資料就往低地址（BOS）移動。`OSTaskStkChk()` 從 BOS 往上掃描，數出連續為 0 的 word 數量，即為 `OSFree`。

> 若 `OSUsed` 接近 `OSFree + OSUsed`（Total），代表 Stack 快要溢出，需要增加 Stack 大小或減少任務的區域變數。

## Task3 的「故意搞壞」設計
---

Task3 的程式碼藏了一個刻意設計的陷阱，目的是讓你在儀錶板上親眼看到 Stack 監控的效果：

```c
void  Task3 (void *data)
{
    char    dummy[500];  // ★ 在 Stack 上宣告 500 bytes 的區域變數！
    INT16U  i;

    for (i = 0; i < 499; i++) {
        dummy[i] = '?';  // ★ 確保這塊 Stack 被真的「碰過」，讓 StkChk 認得出來
    }
    for (;;) {
        // 顯示逆時針轉輪...
        OSTimeDly(20);
    }
}
```

這段程式的教學目的：讓你在 EX2 的儀錶板上，親眼看到 Task3 的 `Used Stack` 比其他任務**高出約 500 words**，直接感受 Stack 監控的效果。如果 `Used ≈ Total`（Free 接近 0），就代表 Stack 即將溢出——這在 RTOS 中是致命錯誤，Stack 往下長太多會覆蓋到相鄰記憶體。

## 郵件箱通訊（Mailbox）— Task4 ↔ Task5
---

EX2 中 Task4 和 Task5 展示了 Mailbox 的「**一問一答（Handshake）**」模式：

```c
OS_EVENT *AckMbox;   // 確認信箱：Task5 用來回覆 Task4「我收到了」
OS_EVENT *TxMbox;    // 傳送信箱：Task4 用來把字母傳給 Task5

// 在 TaskStart 裡建立
AckMbox = OSMboxCreate((void *)0);  // 初始值為空
TxMbox  = OSMboxCreate((void *)0);  // 初始值為空
```

### Task4（發送者）

```c
void  Task4 (void *data)
{
    char  txmsg = 'A';
    INT8U err;

    for (;;) {
        OSMboxPost(TxMbox, (void *)&txmsg);  // 1. 把字母指標塞進 TxMbox
        OSMboxPend(AckMbox, 0, &err);        // 2. 等待 Task5 回覆確認，自己進入 Block
        txmsg++;                             // 3. 收到確認後，準備下一個字母
        if (txmsg == 'Z') txmsg = 'A';
    }
}
```

### Task5（接收者）

```c
void  Task5 (void *data)
{
    char  *rxmsg;
    INT8U  err;

    for (;;) {
        rxmsg = (char *)OSMboxPend(TxMbox, 0, &err); // 1. 等待 Task4 的字母，自己進入 Block
        PC_DispChar(70, 18, *rxmsg, ...);             // 2. 把字母顯示出來
        OSTimeDlyHMSM(0, 0, 1, 0);                   // 3. 等 1 秒（故意慢）
        OSMboxPost(AckMbox, (void *)1);               // 4. 發確認給 Task4
    }
}
```

### Mailbox vs Semaphore — 關鍵差異

| | Semaphore | Mailbox |
| :--- | :--- | :--- |
| **傳遞內容** | 無（只有「信號」） | 一個指標（可以指向任何資料） |
| **容量** | 計數器（0～N） | **只能裝 1 個訊息**，若已有訊息再 Post 會回傳錯誤 |
| **使用場景** | 互斥鎖／資源計數 | 任務間傳遞「一筆資料」的指標 |

## 浮點數空間預留 — `OSTaskStkInit_FPE_x86`
---

### 為什麼 FPU 在 RTOS 中需要特別處理？

x86 的 FPU（浮點運算單元）有一組**獨立的暫存器**：ST0～ST7（浮點數堆疊）以及控制字、狀態字等，共約 94 bytes。

uC/OS-II 的 Context Switch 預設只儲存一般 CPU 暫存器（AX、BX、SP 等），**不儲存 FPU 暫存器**。這會造成靜默算錯：

```
Task A 正在計算 cos(30°)，算到一半被切走
  → ST0 裡是 Task A 的中間結果
Task B 開始執行，也用到 FPU
  → ST0 被 Task B 的數值覆蓋
Task A 恢復執行
  → 以為 ST0 是自己的結果，繼續算
  → 答案錯誤，且不崩潰、不報錯——靜默輸出垃圾數字
```

→ 浮點錯誤比崩潰更危險，因為你不知道它出問題了。

### EX2 的解法：`OSTaskStkInit_FPE_x86`

EX2 用手動方式為 `TaskStart` 保留 FPU 暫存器空間：

```c
ptos = &TaskStartStk[TASK_STK_SIZE - 1];  // Stack 頂（Top Of Stack）
pbos = &TaskStartStk[0];                  // Stack 底（Bottom Of Stack）
size = TASK_STK_SIZE;

OSTaskStkInit_FPE_x86(&ptos, &pbos, &size); // ★ 在 Stack 頂端額外挪出 FPU 暫存器空間
OSTaskCreateExt(TaskStart, ..., ptos, ..., pbos, size, ...);
```

`OSTaskStkInit_FPE_x86()` 做的事：在 Stack 頂端往上再挪出約 94 bytes，專門給 Context Switch 時存放 FPU 快照，並同步修正 `ptos`、`pbos`、`size` 三個變數，讓 Stack 監控數字仍然準確。

### 為什麼要在 OSTaskCreateExt 之前呼叫？

這是這段程式碼最容易讓人困惑的地方。理解的關鍵是：**Context Switch 儲存 FPU 狀態時，會寫入 Stack 頂端之上的 94 bytes**。

如果不事先預留，Stack 的布局會是：

```
高地址  TaskStartStk[511]   ← 原始 ptos（array 邊界）
        [一般 CPU context frame]   ← OSTaskCreateExt 放在這裡
低地址  TaskStartStk[0]
```

Context Switch 要把 FPU 快照存到 `ptos` 以上的位置，但 `TaskStartStk[511]` 已經是 array 的最高位置，再往上寫就是越界，覆蓋到其他變數的記憶體。

`OSTaskStkInit_FPE_x86` 的作用是在呼叫 `OSTaskCreateExt` 之前，先把 `ptos` **往下移 94 bytes**：

```
高地址  TaskStartStk[511]
        ← 94 bytes 保留區（FPU 快照專用）
        ← 修正後的 ptos  ← 傳給 OSTaskCreateExt 的值
        [一般 CPU context frame]
低地址  TaskStartStk[0]
```

`OSTaskCreateExt` 拿到修正後的 `ptos`，把 context frame 放在正確位置，不會碰到頂端的 FPU 保留區。Context Switch 存 FPU 狀態時，頂端剛好有空間可用。同時 `pbos` 和 `size` 也被同步修正，讓 `OSTaskStkChk()` 的統計數字仍然準確。

### 為什麼只有 TaskStart 用這個方法？

EX2 只有 `TaskStart` 實際執行浮點運算（其他任務都是純整數操作），所以只需要為它保留 FPU 空間。若有其他任務也用浮點，就必須對每個任務各自呼叫一次 `OSTaskStkInit_FPE_x86`，手動管理每個任務的 ptos/pbos/size——這個方式在任務數量多時會相當繁瑣，但概念上是相同的。

## 總結：EX2 新增了什麼？
---

| 主題 | EX1 | EX2 |
| :--- | :---: | :---: |
| 任務建立方式 | `OSTaskCreate` | `OSTaskCreateExt` |
| Stack 監控 | ❌ | ✅ `OSTaskStkChk()` |
| IPC 機制 | `OSSemPend/Post` | `OSMboxCreate/Pend/Post` |
| 浮點空間預留 | ❌ | ✅ `OSTaskStkInit_FPE_x86` |
| 任務數量 | 11（1 Start + 10 identical） | 7（各有不同職責） |
