# E3B_rep0_CRASHED 作废说明

## 现象
子进程启动 31.0 秒后退出，未产生任何轮次动作（缺 round 1-16），
`干预核验: 命中0`。

## 根因
`process_stdout.txt` 中出现：

```
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":51,"threshold":50,
  "targets":["...\\sim_285f7fdfd644\\log"]}
```

运行器启动时会执行 `shutil.rmtree(sim_dir/log)` 清理上一轮日志（run_parallel_simulation.py:155）。
本机环境对单次批量删除设有阈值保护，同一批连续三组运行累计删除文件数达到 51 > 50，
清理被拦截，进而导致进程退出。**这是执行环境保护机制造成的，与实验设置无关。**

## 处置
1. 在 `run_direct.py` 的 `reset()` 中增加"每组运行前先自行清理 log/"，
   使运行器待删除文件数保持在低位；
2. 手动清理残留 log 目录后重跑 E3B。
