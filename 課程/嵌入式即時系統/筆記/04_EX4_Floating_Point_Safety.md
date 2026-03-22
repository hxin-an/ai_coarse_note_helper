# 嵌入式即時系統 — uC/OS-II EX4 深度解析：浮點運算在 RTOS 中的致命陷阱與解法
> 來源：`EX4_x86L.FP\BC45\SOURCE\TEST.C` | 產生日期：2026-03-21

## 前言
---

EX4 看起來跟 EX1 非常像——同樣是 10 個結構相同的任務、同樣是一個無窮迴圈、同樣使用 `OSTimeDly(1)`。但它解決的問題比任何一個前面的範例都更隱藏、更危險：**在 RTOS 中，浮點運算預設是不安全的**。這個問題不會讓程式崩潰，也不會回報錯誤，只會靜默地輸出垃圾數字——這比崩潰更難除錯，因為你甚至不知道它出問題了。

## 大綱
---

- [為什麼浮點運算在 RTOS 中是陷阱？](#為什麼浮點運算在-rtos-中是陷阱)
- [解法：`OS_TASK_OPT_SAVE_FP`](#解法os_task_opt_save_fp)
- [EX4 的 Task 函數 — 浮點運算的實際使用](#ex4-的-task-函數--浮點運算的實際使用)
- [`FP32` 是什麼型別？](#fp32-是什麼型別)
- [EX1 vs EX4 — 看起來像，但差了這一個關鍵](#ex1-vs-ex4--看起來像但差了這一個關鍵)
- [總結：什麼時候該加 `OS_TASK_OPT_SAVE_FP`？](#總結什麼時候該加-os_task_opt_save_fp)

## 為什麼浮點運算在 RTOS 中是陷阱？
---

### Context Switch 的本質

任務切換（Context Switch）時，OS 需要把「被切走的任務」用到的 CPU 暫存器狀態全部儲存起來，等任務恢復時再還原。這就像你下棋被打斷，必須先把棋盤的狀態拍照記錄，等你回來再按照照片繼續下。

uC/OS-II 的 `OS_CPU_A.ASM`（x86 的 Context Switch 程式碼）預設儲存：

```
AX, BX, CX, DX, SI, DI, BP, DS, ES, SS, SP, IP, Flags...
```

**但它預設「不儲存」FPU 暫存器：**

```
ST0～ST7（浮點數堆疊）
FPU 控制字、狀態字、標記字...
```

### 靜默算錯的場景

假設 Task A 正在計算 `cos(30°)`，計算到一半被切走。此時 `ST0` 暫存器裡存的是 Task A 的中間結果。接著 Task B 開始執行，它也呼叫 `cos(45°)`，**直接覆蓋了 `ST0` 的值**。等 Task A 恢復執行，它以為 `ST0` 裡的是自己的計算結果，但實際上那是 Task B 留下的殘值 → **答案錯誤，且不報錯、不崩潰、靜默地輸出垃圾數字。**

就像你和另一個同學共用同一個計算機，你按到一半出去上廁所，他趁機按了一堆別的數字，你回來繼續按，算出來的答案完全是亂的，但計算機不會提醒你。

## 解法：`OS_TASK_OPT_SAVE_FP`
---

EX4 只是在建立任務時加了一個 flag，就解決了整個問題：

```c
// EX4 中建立 10 個任務的迴圈
for (i = 0; i < N_TASKS; i++) {
    prio        = i + 1;
    TaskData[i] = prio;
    OSTaskCreateExt(Task,
                    (void *)&TaskData[i],
                    &TaskStk[i][TASK_STK_SIZE - 1],
                    prio,
                    0,
                    &TaskStk[i][0],
                    TASK_STK_SIZE,
                    (void *)0,
                    OS_TASK_OPT_SAVE_FP);  // ★ 這一個 flag 解決所有問題
}
```

`OS_TASK_OPT_SAVE_FP` 告訴 OS：「這個任務會用到 FPU，每次 Context Switch 時，請幫我把 FPU 的全部暫存器也一起存起來，還原時也一起還原。」

實際操作是在每個任務的 Stack 頂端**額外保留一塊空間**，專門放 FPU 暫存器快照。Context Switch 時多做兩個動作：

```
FNSAVE [stack area]  ; 把 FPU 所有狀態存到 Stack 的保留區
(... 一般 Context Switch 流程 ...)
FRSTOR [stack area]  ; 把下一個任務的 FPU 狀態從 Stack 的保留區還原
```

### 加與不加的代價比較

| | 不加 `OS_TASK_OPT_SAVE_FP` | 加了 `OS_TASK_OPT_SAVE_FP` |
| :--- | :--- | :--- |
| Context Switch 速度 | 快 | 稍慢（多了 FNSAVE/FRSTOR） |
| Stack 使用量 | 較少 | 多出約 94 bytes（x87 FPU 狀態大小） |
| 浮點計算安全性 | ❌ 不安全（靜默算錯） | ✅ 安全（每個任務獨立 FPU 狀態） |
| 適用情境 | 任務完全不用浮點數 | 任務使用 `float`/`double`/三角函數 |

## EX4 的 Task 函數 — 浮點運算的實際使用
---

10 個 Task 全部相同，每個任務根據自己的優先權編號計算一個不同起始角度的 cos/sin，並持續旋轉：

```c
void  Task (void *pdata)
{
    FP32   x;          // FP32 = float（32-bit 浮點數）
    FP32   y;
    FP32   angle;
    FP32   radians;
    char   s[81];
    INT8U  ypos;

    ypos  = *(INT8U *)pdata + 7;                        // 決定要顯示在螢幕的第幾行
    angle = (FP32)(*(INT8U *)pdata) * (FP32)36.0;       // 起始角度：任務 1 從 36°，任務 2 從 72°...

    for (;;) {
        radians = (FP32)2.0 * (FP32)3.141592 * angle / (FP32)360.0; // 角度轉弧度
        x       = cos(radians);   // ★ 使用 FPU 的三角函數
        y       = sin(radians);   // ★

        sprintf(s, "   %2d       %8.3f  %8.3f     %8.3f",
                *(INT8U *)pdata, angle, x, y);   // 輸出：優先權, 角度, cos, sin
        PC_DispStr(0, ypos, s, ...);

        if (angle >= (FP32)360.0) {
            angle  = (FP32)0.0;    // 轉滿一圈歸零
        } else {
            angle += (FP32)0.01;   // 每次遞增 0.01 度
        }
        OSTimeDly(1);              // 延遲一個 tick，讓其他任務有機會執行
    }
}
```

> 為什麼要用 `(FP32)36.0` 而不是直接寫 `36.0`？在 C 語言中，`36.0` 預設是 `double`（64-bit）。`(FP32)36.0` 強制轉成 `float`（32-bit），確保所有計算都在 32-bit 精度下進行，避免 FPU 在 32-bit 和 64-bit 模式間切換造成額外問題。

## `FP32` 是什麼型別？
---

在 uC/OS-II 的型別定義中，`FP32` 其實就是 `float` 的別名：

```c
typedef  float   FP32;   // 32-bit 單精度浮點數
typedef  double  FP64;   // 64-bit 雙精度浮點數
```

uC/OS-II 用 `FP32`、`FP64` 而非直接寫 `float`、`double`，是為了讓程式碼在移植到不同平台時更有彈性——有些嵌入式 CPU 的 `float` 可能是 16-bit。

## EX1 vs EX4 — 看起來像，但差了這一個關鍵
---

| | EX1 | EX4 |
| :--- | :--- | :--- |
| 任務數 | 10 | 10 |
| 任務建立 | `OSTaskCreate` | `OSTaskCreateExt` |
| 任務內容 | 在隨機位置顯示字元 | 計算並顯示 cos/sin |
| FPU 保護 | ❌ 無（因為沒有用浮點） | ✅ `OS_TASK_OPT_SAVE_FP` |
| 共享保護 | Semaphore 保護 `random()` | 無需（每個任務操作自己的角度，無共享） |

## 總結：什麼時候該加 `OS_TASK_OPT_SAVE_FP`？
---

判斷規則很簡單——任務的程式碼裡有任何下列情況，就**必須加** `OS_TASK_OPT_SAVE_FP`：

| 情況 | 說明 |
| :--- | :--- |
| 宣告 `float` 或 `double` 型別的變數 | 只要有浮點變數就需要 |
| 呼叫 `sin` / `cos` / `sqrt` / `pow` 等數學函數 | 這些函數內部使用 FPU |
| 用 `%f` / `%lf` 格式化字串（`sprintf` 等） | `sprintf` 處理浮點格式時使用 FPU |
| 進行任何浮點數的加減乘除 | 浮點四則運算全部走 FPU |

**不需要加的情況**：任務完全只用整數（`int`, `INT8U`, `INT16U` 等）。

> 加了 `OS_TASK_OPT_SAVE_FP` 之後，每個任務的 Stack 會多消耗約 94 bytes。在記憶體有限的嵌入式系統上，應該**只對真正需要浮點運算的任務加這個 flag**，而不是「保險起見全部都加」。
