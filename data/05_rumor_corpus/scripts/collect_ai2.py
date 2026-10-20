#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定向补采：AI 造谣 / 打谣 专项（覆盖三个事件）。"""
import json, time, random, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect_search import ev, JS_TPL, RAW, EVENTS

TERMS = ['AI造谣', '打谣', 'AI 合成 图片', '生成 视频 辟谣']


def main():
    tasks = []
    for ev_name, (d1, d2, kw) in EVENTS.items():
        for t in TERMS:
            tasks.append((ev_name, 'B', kw + ' ' + t, d1, d2))
    print(f'定向检索 {len(tasks)} 组', flush=True)
    for ev_name, sl, q, d1, d2 in tasks:
        out_path = os.path.join(RAW, f'search_{ev_name}.jsonl')
        got = 0
        for page in range(1, 3):
            js = JS_TPL % (json.dumps(q, ensure_ascii=False), d1, d2, page)
            data, err = ev(js)
            if err or not isinstance(data, dict):
                print(f'  ! {q} p{page} {str(err)[:80]}', flush=True)
                time.sleep(8)
                continue
            rows = data.get('rows') or []
            if not rows:
                break
            got += len(rows)
            with open(out_path, 'a', encoding='utf-8') as f:
                for r in rows:
                    r.update(event=ev_name, slice_hint=sl, query=q,
                             date_from=d1, date_to=d2, page=page)
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            time.sleep(random.uniform(2.2, 3.4))
        print(f'  {ev_name:<12} {q:<18} -> {got}', flush=True)
        time.sleep(random.uniform(2.0, 3.0))


if __name__ == '__main__':
    main()
