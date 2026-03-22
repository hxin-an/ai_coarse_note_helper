# 嵌入式即時系統 — uC/OS-II EX1 編譯流程與執行架構深度解析
> 來源：`EX1_x86L\BC45\SOURCE\TEST.C` / `MAKETEST.BAT` / `TEST.MAK` | 產生日期：2026-03-21

## 前言
---

拿到一個 uC/OS-II 範例專案，第一件困惑的事往往不是「程式在做什麼」，而是「這些檔案是怎麼變成一個可以執行的程式的」。本文件從批次檔 `MAKETEST.BAT` 出發，逐步拆解整個建置流程（Build Pipeline）——從原始碼如何被翻譯成機器碼、多個目標檔如何被拼接成執行檔——再進入 `TEST.C` 的執行架構，理解 RTOS 程式啟動後任務是如何被排程與管理的。

## 大綱
---

- [執行環境與步驟](#執行環境與步驟)
- [建置流程起點：`MAKETEST.BAT`](#建置流程起點maketest-bat)
- [嵌入式開發常見副檔名對照](#嵌入式開發常見副檔名對照)
- [編譯規則與相依性：`TEST.MAK`](#編譯規則與相依性testmak)
  - [步驟 A：定義工具路徑與變數](#步驟-a定義工具路徑與變數)
  - [步驟 B：設定編譯參數](#步驟-b設定編譯參數)
  - [步驟 C：定義檔案相依性（生成 `.OBJ`）](#步驟-c定義檔案相依性生成-obj)
  - [步驟 D：連結成 `TEST.EXE`](#步驟-d連結成-testexe)
- [功能組態設定：`OS_CFG.H`](#功能組態設定os_cfgh)
- [系統啟動：`main()` 的暫時性](#系統啟動main-的暫時性)
- [任務的運作機制](#任務的運作機制)
- [啟動任務（TaskStart）— 系統的第一個任務](#啟動任務taskstart--系統的第一個任務)
- [核心運作 3 要素](#核心運作-3-要素)
  - [系統時鐘滴答（Clock Tick）](#系統時鐘滴答clock-tick)
  - [任務狀態阻塞（`OSTimeDly`）](#任務狀態阻塞ostimedly)
  - [資源互斥與同步（Semaphore）](#資源互斥與同步semaphore)
- [EX1 的設計目的](#ex1-的設計目的)

## 執行環境與步驟
---

EX1 是為 x86 DOS 環境撰寫的程式，在現代 Windows 上需透過 **DOSBox** 模擬 DOS 環境才能執行。

### 掛載與執行

```bat
:: 1. 在 DOSBox 裡把包含 SOFTWARE 資料夾的目錄掛載為 C 槽
mount c <本機路徑>        :: 例如：mount c D:\ucosii

:: 2. 切換到 EX1 的 SOURCE 目錄
cd c:\SOFTWARE\uCOS-II\EX1_x86L\BC45\TEST

:: 3. 執行批次檔（自動編譯）
maketest.bat

:: 4. 執行編譯好的程式
test.exe
```

### 為什麼需要 DOSBox？

uC/OS-II 的 x86 移植版直接操作 DOS IVT（中斷向量表）、8254 計時器晶片與 VGA 文字模式——這些都是 16-bit 實模式（Real Mode）的硬體操作。現代 64-bit Windows 不支援執行 16-bit DOS 程式，DOSBox 提供完整的 DOS 硬體模擬環境。

## 建置流程起點：`MAKETEST.BAT`
---

在命令列環境中，執行 `MAKETEST.BAT` 來自動化建置過程。這個批次檔的主要功能是建立暫存環境並呼叫編譯工具。

```bat
MD    ..\WORK           :: 建立 WORK 目錄，作為編譯時的暫存工作區
MD    ..\OBJ            :: 建立 OBJ 目錄，存放編譯好的 .OBJ 目標檔
MD    ..\LST            :: 建立 LST 目錄，存放編譯與連結過程中的列表檔
CD    ..\WORK           :: 切換到 WORK 工作目錄
COPY  ..\TEST\TEST.MAK   TEST.MAK  :: 複製 MAKEFILE 到工作目錄
C:\BC45\BIN\MAKE -f TEST.MAK       :: 呼叫 Borland C++ 的 MAKE 工具
CD    ..\TEST           :: 編譯完成後返回 TEST 目錄
```

此腳本將環境建構好後，實際的編譯與連結工作交給 `MAKE` 工具與 `TEST.MAK` 來處理。

## 嵌入式開發常見副檔名對照
---

在繼續往下看 Makefile 的規則之前，先釐清各種副檔名的檔案在整個編譯流程中扮演的角色：

| 副檔名 | 類型名稱 | 目的與功能 |
| :--- | :--- | :--- |
| **`.BAT`** | 批次檔（Batch File） | 自動執行一連串命令列指令的腳本，例如 `MAKETEST.BAT` 負責建目錄、複製檔案、呼叫編譯器。 |
| **`.MAK`** | Make 腳本（Makefile） | 定義專案**編譯規則**的檔案，告訴編譯器「誰依賴誰、誰該先編譯」，達成自動化編譯。 |
| **`.C`** | C 語言原始碼 | 人類可讀的程式邏輯，例如 `TEST.C`（你的應用程式）或 `uCOS_II.C`（作業系統主程式）。 |
| **`.H`** | 標頭檔（Header File） | 存放變數宣告、常數定義（`#define`）或函式原型。`.C` 檔案透過 `#include` 引入。 |
| **`.ASM`** | 組合語言檔（Assembly） | 比 C 語言更底層，直接控制 CPU 暫存器。任務切換（Context Switch）因為需要操作 CPU 暫存器，所以必須寫在 `OS_CPU_A.ASM` 裡。 |
| **`.OBJ`** | 目標檔（Object File） | 原始碼經過編譯器翻譯後的**純機器碼片段**。此時雖然已是機器碼，但還缺乏完整的記憶體地址——`TEST.OBJ` 裡雖然呼叫了 `OSInit()`，但它不知道 `OSInit()` 放在哪個記憶體位址，所以 `.OBJ` 無法獨立執行。 |
| **`.EXE`** | 執行檔（Executable） | 由連結器（Linker）將多塊 `.OBJ` 拼圖組合後產生的最終成品。連結器負責**補齊所有遺失的地址**，讓各種碎片能彼此相連，打包成作業系統可以載入執行的格式。 |

> 關鍵概念：`.OBJ` 是「拼圖碎片」，`.EXE` 是「拼湊完成的成品」。連結器（TLINK）做的事，就是把所有碎片的缺口（未知地址）補齊，拼成一個整體。

## 編譯規則與相依性：`TEST.MAK`
---

`TEST.MAK`（也就是 Makefile）是整個專案建置的核心，告訴 `MAKE` 工具「有哪些檔案需要編譯、編譯時下什麼參數、最後怎麼把所有東西組裝成 `.EXE`」。

### 步驟 A：定義工具路徑與變數

在撰寫 Makefile 時，先把常用的路徑定義成變數，後面用 `$(變數名稱)` 代入，讓程式碼更簡潔：

```makefile
BORLAND=C:\BC45                 # 定義 Borland C++ 編譯器的安裝路徑

CC=$(BORLAND)\BIN\BCC           # C 語言編譯器 (BCC)
ASM=$(BORLAND)\BIN\TASM         # 組合語言編譯器 (TASM)
LINK=$(BORLAND)\BIN\TLINK       # 連結器 (TLINK)

OBJ=..\OBJ                      # 目標檔 (.OBJ) 存放位置
SOURCE=..\SOURCE                # C 語言程式碼來源
OS=\SOFTWARE\uCOS-II\SOURCE     # uC/OS-II 作業系統原始碼位置

INCLUDES=      $(SOURCE)\INCLUDES.H  \   # 專案的統一標頭檔入口
               $(SOURCE)\OS_CFG.H    \   # OS 功能開關（決定要編譯進哪些模組）
               $(PORT)\OS_CPU.H      \   # CPU 移植層的型別定義（INT8U 等）
               $(PC)\PC.H            \   # DOS 硬體模擬層的函數宣告
               $(OS)\uCOS_II.H           # uC/OS-II 核心 API 的函數原型與資料結構
```

`INCLUDES` 把所有 `.H` 標頭檔集中成一個清單。Step C 的相依性規則裡寫的 `$(INCLUDES)` 就是引用這個清單——只要任何一個 `.H` 被修改，`MAKE` 就會判定所有依賴它的 `.C` 都需要重新編譯。

### 步驟 B：設定編譯參數

```makefile
C_FLAGS=-c -ml -1 -G -O -Ogemvlbpi -Z -d -n..\obj -k- -v -vi- -wpro -I$(BORLAND)\INCLUDE -L$(BORLAND)\LIB
```

對新手最重要的幾個參數：

| 參數 | 意義 |
| :--- | :--- |
| `-c` | **只編譯不連結**。先把 `.C` 編譯成 `.OBJ`，後面再統一連結。 |
| `-ml` | **使用 Large Memory Model**。早期 x86 有記憶體分段限制，OS 層級的程式必須用這個模式才能妥善管理記憶體。 |
| `-I` | 告訴編譯器去哪裡找標頭檔（Include files）。 |
| `-L` | 告訴編譯器去哪裡找函式庫（Libraries）。 |

### 步驟 C：定義檔案相依性（生成 `.OBJ`）

這是 Makefile 最精華的部分，定義「如果 A 檔案有更新，就必須重新編譯 B 檔案」：

```makefile
# 規則 1：目標（冒號前）與相依性（冒號後）
$(OBJ)\TEST.OBJ:                \
               $(SOURCE)\TEST.C  \
               $(INCLUDES)

# 規則 2：滿足條件時執行的編譯指令
               COPY   $(SOURCE)\TEST.C      TEST.C
               $(CC)  $(C_FLAGS)            TEST.C
```

逐行拆解：
*   **目標（`$(OBJ)\TEST.OBJ:`）**：冒號前代表想要產生的結果。
*   **依賴（`$(SOURCE)\TEST.C` 與 `$(INCLUDES)`）**：冒號後代表要產生這個目標，需要依賴哪些原料。`MAKE` 會檢查檔案最後修改時間，**只有當原料的修改時間比目標還新時，才會觸發底下的編譯指令**。
*   **搬運（`COPY ...`）**：將原料 `TEST.C` 複製到當前工作目錄。
*   **執行編譯（`$(CC) $(C_FLAGS) TEST.C`）**：呼叫 C 編譯器，將文字檔轉為二進位的 `.OBJ` 檔。

對於組合語言（Assembly），作法類似但換用組譯器：

```makefile
$(OBJ)\OS_CPU_A.OBJ:                  \
               $(PORT)\OS_CPU_A.ASM

               COPY   $(PORT)\OS_CPU_A.ASM  OS_CPU_A.ASM
               $(ASM) $(ASM_FLAGS)  $(PORT)\OS_CPU_A.ASM,$(OBJ)\OS_CPU_A.OBJ
```

### 步驟 D：連結成 `TEST.EXE`

當所有 `.C` 與 `.ASM` 都分別編譯成 `.OBJ` 後，這些半成品彼此是互相不認識的，需要連結器（Linker）把它們像拼圖一樣組合起來，補上所有地址：

```makefile
$(TARGET)\TEST.EXE:                  \
               $(OBJ)\OS_CPU_A.OBJ   \
               $(OBJ)\OS_CPU_C.OBJ   \
               $(OBJ)\PC.OBJ         \
               $(OBJ)\TEST.OBJ       \
               $(OBJ)\uCOS_II.OBJ    \
               $(SOURCE)\TEST.LNK

               COPY    $(SOURCE)\TEST.LNK
               $(LINK) $(LINK_FLAGS)     @TEST.LNK
               COPY    $(OBJ)\TEST.EXE   $(TARGET)\TEST.EXE
```

終極目標 `TEST.EXE` 依賴了所有的 `.OBJ` 檔與設定檔 `TEST.LNK`。連結器把核心（`uCOS_II.OBJ`）、底層 CPU 程式（`OS_CPU_A.OBJ`）、硬體溝通（`PC.OBJ`）以及應用程式（`TEST.OBJ`）全部縫合在一起，補齊所有函數地址，結合成可以執行的 `TEST.EXE`。

### TEST.LNK 的格式

`@TEST.LNK` 是 Borland TLINK 的**回應檔（Response File）**——把所有命令列參數寫進一個文字檔，讓 Linker 讀進來執行，避免命令列過長。檔案內容共四段，每行結尾的 `+` 代表「下一行是同一段的延續」：

```
/v /s /c /P-          +    ← 第一段：Linker flags
C:\BC45\LIB\C0L.OBJ   +    ← 第二段：要連結的 .OBJ（C Runtime 啟動碼必須排第一）
..\OBJ\TEST.OBJ       +
..\OBJ\OS_CPU_A.OBJ   +
..\OBJ\OS_CPU_C.OBJ   +
..\OBJ\PC.OBJ         +
..\OBJ\uCOS_II.OBJ
..\OBJ\TEST,..\OBJ\TEST    ← 第三段：輸出路徑（EXE 路徑, MAP 路徑）
C:\BC45\LIB\EMU.LIB   +    ← 第四段：要連結的 .LIB 函式庫
C:\BC45\LIB\MATHL.LIB +
C:\BC45\LIB\CL.LIB
```

| 段落 | 說明 |
| :--- | :--- |
| **Linker flags** | `/v` 含除錯資訊；`/s` 產生詳細符號表；`/c` 大小寫有別；`/P-` 不產生 packed 執行檔 |
| **第一個 .OBJ：`C0L.OBJ`** | Borland C Runtime 的**啟動程式碼**（Large Memory Model）。它包含真正的進入點 `_start`，負責初始化堆疊、清零全域變數，最後呼叫 `main()`。**必須排第一**，Linker 才會把它的 `_start` 寫入 EXE header 的進入點欄位。OS 載入 EXE 後跳到的第一行，就是這裡。 |
| **其餘 .OBJ** | 應用層（`TEST.OBJ`）、CPU 移植層（`OS_CPU_A/C.OBJ`）、PC 硬體層（`PC.OBJ`）、OS 核心（`uCOS_II.OBJ`）→ 順序對 MAKE 無意義，Linker 會自動解析符號；但放在 `C0L.OBJ` 後面是慣例。 |
| **輸出路徑** | 逗號分隔：左側是 `.EXE` 輸出路徑，右側是 `.MAP`（符號對照表）路徑。 |
| **函式庫** | `EMU.LIB` = 浮點模擬（無硬體 FPU 時）；`MATHL.LIB` = 數學函數（Large Model）；`CL.LIB` = C 標準函式庫（Large Model）。 |

> **Makefile 的 `.OBJ` 順序 ≠ LNK 的連結順序**：Makefile Step D 裡列的 `.OBJ` 只是告訴 MAKE「這些東西改了就重建」，實際連結順序完全由 `TEST.LNK` 決定。

## 功能組態設定：`OS_CFG.H`
---

### OS_CFG.H 是什麼？

`OS_CFG.H` 是 uC/OS-II 的**編譯期組態檔**——在建置（編譯）之前決定好，編譯完就鎖死，執行期間不可更改。

`OS_CFG.H` 的每一個 `#define` 都是**條件編譯開關**——它和程式裡普通的 `if` 判斷有本質差異：

```c
// 普通的 if — 程式碼存在於 binary，只是執行期決定要不要跑
if (sem_enabled) {
    OSSemPost(...);   // 這行機器碼永遠在 .EXE 裡
}

// 條件編譯 — 程式碼在 binary 裡根本不存在
#if OS_SEM_EN > 0
void  OSSemPost(...) {    // OS_SEM_EN = 0 時，編譯器看都不看這段
    ...
}
#endif
```

`OS_CFG.H` 裡把某個功能設為 0，等同於告訴編譯器：「這段程式碼不存在。」最終 `.EXE` / 韌體裡**完全沒有**那個功能的機器碼，不占 Flash、不占 RAM。這是嵌入式系統的核心設計哲學：**按需裁剪，不帶多餘的東西出廠**。

### 四類設定項目

**第一類：資源上限（影響記憶體配置）**

| 設定 | EX1 值 | 說明 |
| :--- | :---: | :--- |
| `OS_MAX_TASKS` | 11 | 最多 11 個應用任務（10 個 Task + 1 個 TaskStart）。OS 在初始化時就靜態分配 11 個 TCB 結構體，之後不能動態新增。 |
| `OS_MAX_EVENTS` | 2 | 最多 2 個 Event Control Block（EX1 只用了 1 個 Semaphore）。 |
| `OS_LOWEST_PRIO` | 12 | 允許的最低優先權編號。OS 內部的 Idle Task 固定使用這個編號，Stat Task 使用 `OS_LOWEST_PRIO - 1`。 |
| `OS_TASK_IDLE_STK_SIZE` | 512 | Idle Task 的 Stack 大小（word 數）。 |

**第二類：功能模組開關（0 = 不編譯，1 = 編譯進去）**

| 設定 | EX1 值 | 說明 |
| :--- | :---: | :--- |
| `OS_SEM_EN` | 1 | Semaphore 功能。EX1 用到 `OSSemCreate/Pend/Post`，必須開。 |
| `OS_MBOX_EN` | 1 | Mailbox 功能（EX2 才會用到，但 EX1 也開著）。 |
| `OS_Q_EN` | 1 | Message Queue（EX3 才用）。 |
| `OS_TASK_STAT_EN` | 1 | 統計任務（量測 CPU 使用率）。開了才能呼叫 `OSStatInit()` 和顯示 CPU Usage。 |
| `OS_CPU_HOOKS_EN` | 1 | 允許使用者在 Context Switch 等事件插入 Hook 函數（EX3 用到）。 |

**第三類：每個模組的細部 API 開關**

每個功能模組還能進一步只保留用到的 API。例如 Semaphore 模組：

```c
#define OS_SEM_EN          1   // Semaphore 主功能開啟
#define OS_SEM_ACCEPT_EN   1   // 包含 OSSemAccept()（非阻塞版 Pend）
#define OS_SEM_DEL_EN      1   // 包含 OSSemDel()
#define OS_SEM_QUERY_EN    1   // 包含 OSSemQuery()（查詢 Semaphore 狀態）
```

如果你的專案不需要刪除 Semaphore，把 `OS_SEM_DEL_EN` 設為 0，`OSSemDel()` 就不佔空間。

**第四類：時序參數**

```c
#define OS_TICKS_PER_SEC  200  // 每秒 200 次 Tick = 5 ms 解析度
```

這個值直接決定系統的時間解析度，同時也影響 CPU 的 Overhead：200 Hz 代表每秒有 200 次中斷需要處理 `OSTickISR`。值設太高（如 1000 Hz），Tick 處理本身就吃掉大量 CPU；值設太低（如 10 Hz），`OSTimeDly(1)` 就是粗糙的 100 ms，精度不夠。

### OS_CFG.H 與 Makefile 的關係

`OS_CFG.H` 的設定生效，依賴 Makefile 步驟 A 中的這一行：

```makefile
INCLUDES = $(SOURCE)\OS_CFG.H  ...  # OS_CFG.H 是 INCLUDES 的一部分
```

因為所有 `.C` 都依賴 `$(INCLUDES)`，只要修改 `OS_CFG.H`，MAKE 就會觸發**全部重新編譯**，確保新的開關設定被所有原始碼讀到。

## 系統啟動：`main()` 的暫時性
---

編譯出 `TEST.EXE` 後，執行會進入 `TEST.C` 中的 `main()`。在 RTOS 中，`main()` 的職責**僅是進行環境初始化與啟動系統核心**，啟動後就將控制權完全交給 OS：

```c
void  main (void) {
    OSInit();                  // 1. 初始化 uC/OS-II 內部變數與資料結構（TCB 表、Event Queue）
    PC_DOSSaveReturn();        // 2. 備份原有 DOS 狀態（設定定時中斷前必須先保存）
    PC_VectSet(uCOS, OSCtxSw); // 3. 把 IVT[0x80] 設為 OSCtxSw：處理主動（Voluntary）Context Switch

    // 4. 建立系統的第一個應用層任務：TaskStart（優先等級 0，最高權限）
    OSTaskCreate(TaskStart, (void *)0, &TaskStartStk[TASK_STK_SIZE - 1], 0);

    OSStart();                 // 5. 正式啟動多工排程。此函數不會返回，後續完全由 uC/OS-II 接管
}
```

### `PC_VectSet(uCOS, OSCtxSw)` — 為主動切換設定跳轉目標

uC/OS-II 的 Context Switch 有兩條觸發路徑：

| | Voluntary（主動） | Involuntary（被動） |
| :--- | :--- | :--- |
| **觸發者** | 任務自己（呼叫 `OSSemPend`、`OSTimeDly` 等） | Timer ISR（`OSTickISR`） |
| **機制** | 執行 `INT 0x80` → CPU 查 IVT → 跳到 `OSCtxSw` | `OSTickISR` 結束前直接呼叫 `OSIntCtxSw` |
| **任務知道嗎？** | 知道（自己主動讓出） | 不知道（被強制切走） |

`PC_VectSet(uCOS, OSCtxSw)` 只負責設定 **Voluntary** 那條路——把 `INT 0x80` 的跳轉目標寫進 IVT。若這行沒設，任務呼叫 blocking 函數時 CPU 會跳到 DOS 預設的 0x80 中斷處理程式，Context Switch 完全失效。Involuntary 那條路（`OSIntCtxSw`）是 Timer ISR 直接呼叫的，不經過 IVT。

### 靜態 RTOS vs 動態 OS

uC/OS-II 是**靜態 RTOS**，與 Linux 這類動態 OS 的根本差異在於「任務從哪裡來、能不能臨時新增」：

| | uC/OS-II（靜態） | Linux（動態） |
| :--- | :--- | :--- |
| **任務來源** | 編譯期寫死在程式碼裡 | 執行期隨時 `fork()` / `exec()` 新程式 |
| **任務數上限** | `OS_MAX_TASKS`（編譯期常數，改了要重編） | 動態，受實體記憶體與 OS 限制 |
| **新增任務方式** | 改 `.C` → 重新編譯 → 重新燒錄韌體 | 直接執行一個新的可執行檔 |
| **Stack 配置** | 靜態陣列，編譯期就決定大小 | OS 動態分配，可增長（mmap） |
| **行為可預測性** | ✅ 高——所有任務出廠前就已知 | ❌ 低——任何時刻可能有未知程序啟動 |
| **適用場合** | 嵌入式、即時控制系統 | 通用桌機／伺服器 |

→ 靜態設計是優點，不是限制：嵌入式系統**不需要**執行期動態載入程式，換來的是完全可預測的時序行為與最小化的記憶體佔用。

## 任務的運作機制
---

進入多工作業模式後，系統由多個**任務（Tasks）**組成，各有以下技術特質：

**無窮迴圈**：任務多半設計為 `for(;;)`，代表它會持續等待事件發生並進行處理。

**私有的堆疊（Stack）**：`OSTaskCreate` 的第三個參數定義了 `TaskStartStk`，每個任務都有自己獨立的 Stack，用來儲存暫存器狀態與區域變數。

**優先權搶佔（Preemptive）**：uC/OS-II 是優先權搶佔式核心，優先權數字越低、權力越大。一旦高優先權任務變為 Ready 狀態，它會立刻中斷當前較低優先權任務的執行。

## 啟動任務（TaskStart）— 系統的第一個任務
---

`main()` 只建立一個任務：`TaskStart`，優先權 0（最高）。`OSStart()` 之後，OS 第一個跑的就是它。**TaskStart 的設計模式是 uC/OS-II 的標準慣例**：把所有初始化集中在這裡做，做完後變成一個普通的週期性任務，負責監控系統狀態。

### TaskStart 的執行順序

```c
void  TaskStart (void *pdata)
{
    // 1. 初始化螢幕顯示框架
    TaskStartDispInit();

    // 2. 進入臨界區，設定 Clock Tick（必須關中斷才能安全改中斷向量）
    OS_ENTER_CRITICAL();
    PC_VectSet(0x08, OSTickISR);      // 攔截 x86 硬體 Timer 0 中斷（IRQ 0）
    PC_SetTickRate(OS_TICKS_PER_SEC); // 把 Timer 頻率設為 OS_CFG.H 定義的值（EX1 = 200 Hz）
    OS_EXIT_CRITICAL();

    // 3. 初始化 OS 統計任務（量測 CPU 使用率的背景任務）
    OSStatInit();

    // 4. 建立應用層的 10 個工作任務
    TaskStartCreateTasks();

    // 5. 進入無窮迴圈：每秒更新一次儀錶板
    for (;;) {
        TaskStartDisp();          // 顯示目前任務數、CPU 使用率、Context Switch 次數
        if (PC_GetKey(&key) == TRUE) {
            if (key == 0x1B) {
                PC_DOSReturn();   // 按 ESC → 恢復 DOS 環境並退出
            }
        }
        OSCtxSwCtr = 0;           // 將計數器歸零（配合每秒顯示「每秒切換次數」）
        OSTimeDlyHMSM(0, 0, 1, 0); // 延遲 1 秒，讓其他任務有 CPU 可用
    }
}
```

### 為什麼 Tick ISR 要在 TaskStart 裡安裝，而不是在 main() 裡？

一旦安裝 `OSTickISR`，Timer 中斷就會立刻以 200 Hz 觸發，OS 排程器隨時可能被呼叫。若在 `OSStart()` 之前就安裝，排程器還沒準備好，Context Switch 會出錯。

**正確順序**：

```
main()
  ├─ OSInit()                        // 初始化 OS 內部結構
  ├─ PC_VectSet(uCOS, OSCtxSw)       // 安裝 Voluntary Context Switch handler（不會立刻觸發）
  ├─ OSTaskCreate(TaskStart, ...)    // 建立第一個任務
  └─ OSStart()                       // OS 接管 CPU，進入 TaskStart

TaskStart()
  ├─ OS_ENTER_CRITICAL()
  ├─ PC_VectSet(0x08, OSTickISR)     // ★ 這裡才安裝 Tick ISR — OS 已完全就緒
  ├─ PC_SetTickRate(200)
  └─ OS_EXIT_CRITICAL()
```

→ `OSCtxSw` 在 `main()` 就可以裝，因為它是被動等待 `INT 0x80` 觸發，不會自己跑。`OSTickISR` 則必須等 OS 跑起來後才裝，否則中斷一來排程器還沒初始化就爆炸。

### 為什麼 Clock Tick 設定要包在 `OS_ENTER_CRITICAL()` 裡？

`OS_ENTER_CRITICAL()` 和 `OS_EXIT_CRITICAL()` 是關閉/恢復 CPU 中斷的巨集。修改中斷向量表是**不可被打斷的操作**——如果改到一半來了一個中斷，舊向量已被覆蓋、新向量還沒寫完，CPU 跳到的地址會是垃圾值 → 系統當機。包在 Critical Section 裡確保這兩行原子完成。

### TaskStartCreateTasks()：建立 10 個相同任務

```c
static  void  TaskStartCreateTasks (void)
{
    INT8U  i;
    for (i = 0; i < N_TASKS; i++) {         // N_TASKS = 10
        TaskData[i] = '0' + i;              // 每個任務帶入自己的字元（'0'～'9'）
        OSTaskCreate(Task,
                     (void *)&TaskData[i],  // 透過參數告訴任務「你是第幾號」
                     &TaskStk[i][TASK_STK_SIZE - 1],  // Stack 頂端
                     i + 1);               // 優先權 1～10（TaskStart 是 0，最高）
    }
}
```

10 個任務函數體完全相同（都是 `Task()`），靠傳入不同的 `pdata` 讓各自在螢幕上顯示不同字元。優先權 1 最高、10 最低，但因為每個任務跑完就 `OSTimeDly(1)` 讓出 CPU，實際上輪替非常均勻。

## 核心運作 3 要素
---

### 系統時鐘滴答（Clock Tick）

Clock Tick 是整個 RTOS 計時機制的基礎。沒有 Tick，`OSTimeDly`、`OSTimeDlyHMSM`、逾時等待全部失效——OS 不知道時間在走。

```c
PC_VectSet(0x08, OSTickISR);      // 把 x86 Timer 0（IRQ 0）的中斷服務程式換成 OSTickISR
PC_SetTickRate(OS_TICKS_PER_SEC); // OS_TICKS_PER_SEC = 200 → 每秒產生 200 次中斷
```

每次 Timer 0 中斷觸發，`OSTickISR` 就執行一次，它做兩件事：
1. 把所有正在「延遲倒數」的任務計數器減 1，倒數到 0 的任務回到 Ready 狀態
2. 呼叫排程器，看看有沒有比當前任務優先權更高的任務剛變成 Ready → 若有，立刻切換

`OS_TICKS_PER_SEC = 200` 代表 Tick 解析度為 $\frac{1}{200} = 5\text{ ms}$。`OSTimeDly(1)` = 至少等 5 ms；`OSTimeDlyHMSM(0,0,1,0)` = 等 200 Ticks = 1 秒。

### 任務狀態阻塞（`OSTimeDly`）

```c
OSTimeDly(1); // 延遲當前任務 1 個 Clock Tick（≈ 5 ms）
```

這一行做的事情不只是「等一下」，它是 EX1 能讓 10 個任務「輪流跑」的關鍵機制：

1. 呼叫 `OSTimeDly(1)` → 當前任務的狀態從 **Running** 改成 **Waiting（計時 1 Tick）**
2. OS 立刻呼叫排程器，選出目前 Ready 狀態中優先權最高的任務給 CPU
3. 1 個 Tick 後（下一次 `OSTickISR`），這個任務回到 **Ready** 狀態，等待被排到

如果沒有這一行，優先權最高的任務（Task 1）會永遠佔著 CPU，其他任務永遠跑不到。

### 資源互斥與同步（Semaphore）

EX1 中 `random()` 函數和螢幕顯示是**共享資源**——它們不是 Thread-safe 的，10 個任務同時呼叫會互相破壞內部狀態。Semaphore（信號量）解決這個問題：

```c
// main() 裡建立：初始值 = 1（代表「這個資源目前沒人在用，可以進入」）
RandomSem = OSSemCreate(1);

// 每個 Task 的使用方式
OSSemPend(RandomSem, 0, &err); // 嘗試把 Semaphore 從 1 減到 0；若已是 0，進入 Block 等待
x = random(80);                // ← Critical Section：安全地使用共享資源
y = random(16);
PC_DispChar(x, y+5, ...);
OSSemPost(RandomSem);          // 把 Semaphore 從 0 加回 1，喚醒下一個等待的任務
```

`OSSemCreate(1)` 建立的是**二元信號量（Binary Semaphore）**，值只在 0 和 1 之間變動：

| Semaphore 值 | 意義 |
| :--- | :--- |
| **1** | 資源空閒，下一個 `Pend` 可以立刻通過 |
| **0** | 資源被佔用，再來 `Pend` 的任務進入 Block 排隊 |

→ 任何時刻最多只有 1 個任務在 Critical Section 內執行，其他 9 個在 `OSSemPend` 排隊等候。

## EX1 的設計目的
---

EX1 想展示的是**一個最基本的 uC/OS-II 系統長什麼樣子**：「我有 10 個任務同時在跑，他們共享一個資源，但不會打架。」

| 展示項目 | 怎麼做到的 |
| :--- | :--- |
| **多任務並行** | 10 個 Task 輪流在螢幕上顯示自己的字元，看起來像同時在動 |
| **任務主動讓出 CPU** | 每個 Task 跑完就 `OSTimeDly(1)`，不霸佔 CPU |
| **共享資源保護** | `random()` 和螢幕寫入用 Semaphore 包住，確保不互相破壞 |

→ EX1 是一個**最小可運行的 RTOS 範例**，把三個核心概念（多任務、讓出 CPU、互斥鎖）全部塞進一個夠簡單的程式，讓你能一眼看懂每個機制的用途。後面的 EX2～EX4 都是在這個基礎上，每次只多加一個新概念（Stack 監控、Mailbox、浮點保護）。
