#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按互动量优先级补抓媒体/官方热帖评论（切片 C）。"""
import json, os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect_detail import ev, JS_COMMENTS, mblogid_from_href, RAW

PER_EVENT = 14


def main():
    recs = {}
    for fp in glob.glob(os.path.join(RAW, 'search_*.jsonl')):
        for line in open(fp, encoding='utf-8'):
            r = json.loads(line)
            recs.setdefault(r['mid'], r)

    likes = {}
    for line in open(os.path.join(RAW, 'likes.jsonl'), encoding='utf-8'):
        x = json.loads(line)
        if x.get('ok'):
            likes[x['mid']] = x
    done = set()
    cp = os.path.join(RAW, 'comments.jsonl')
    if os.path.exists(cp):
        for line in open(cp, encoding='utf-8'):
            done.add(str(json.loads(line).get('root_mid')))

    media_kw = ['日报', '新闻', '发布', '网警', '公安', '融媒', '电视台', '央视', '新华', '人民',
                '观察', '晚报', '时报', '广播', '宣传', '辟谣', '政府', '应急', '气象', '网信', '政法']
    by_ev = {}
    for mid, r in recs.items():
        if mid in done:
            continue
        if r.get('slice_hint') != 'C' and not any(k in r.get('user', '') for k in media_kw):
            continue
        c = likes.get(mid, {}).get('comments', 0) or 0
        by_ev.setdefault(r['event'], []).append((c, mid, r.get('user', '')))

    picked = []
    for e, lst in by_ev.items():
        lst.sort(reverse=True)
        picked += [{'mid': m, 'user': u, 'maxid': 0, 'event': e} for c, m, u in lst[:PER_EVENT]]
    print(f'优先级补抓 {len(picked)} 帖', [(p["event"], p["mid"]) for p in picked][:3], flush=True)

    total = 0
    for i in range(0, len(picked), 4):
        batch = picked[i:i + 4]
        data, err = ev(JS_COMMENTS % json.dumps([{'mid': b['mid'], 'user': b['user'], 'maxid': 0} for b in batch],
                                                ensure_ascii=False), timeout=240)
        if err or not isinstance(data, list):
            print(f'  ! 批次{i//4} {str(err)[:90]}', flush=True)
            continue
        emap = {b['mid']: b['event'] for b in batch}
        for c in data:
            c['event'] = emap.get(c['root_mid'], '')
        total += len(data)
        with open(cp, 'a', encoding='utf-8') as f:
            for c in data:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f'  {min(i+4, len(picked))}/{len(picked)} 累计 {total}', flush=True)
    print('新增评论', total)


if __name__ == '__main__':
    main()
