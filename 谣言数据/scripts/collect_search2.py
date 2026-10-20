#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补充采集：补齐“人身交通险情”“物资保供”两类语义槽位的语料。"""
import json, time, random, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect_search import ev, JS_TPL, RAW, EVENTS

EXTRA = {
    'A': ['积水 被困', '楼 塌', '航班 取消', '高速 封路', '物资 短缺', '超市 抢购', '停电 没水'],
}


def main():
    tasks = []
    for ev_name, (d1, d2, kw) in EVENTS.items():
        for t in EXTRA['A']:
            tasks.append((ev_name, 'A', kw + ' ' + t, d1, d2))
    print(f'补充检索式 {len(tasks)} 组', flush=True)
    for ev_name, sl, q, d1, d2 in tasks:
        out_path = os.path.join(RAW, f'search_{ev_name}.jsonl')
        got = 0
        for page in range(1, 3):
            js = JS_TPL % (json.dumps(q, ensure_ascii=False), d1, d2, page)
            data, err = ev(js)
            if err or not isinstance(data, dict):
                print(f'  ! {ev_name} | {q} | p{page} {str(err)[:100]}', flush=True)
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
            time.sleep(random.uniform(2.2, 3.6))
        print(f'  {ev_name:<12} {q:<16} -> {got}', flush=True)
        time.sleep(random.uniform(2.0, 3.5))


if __name__ == '__main__':
    main()
