#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微博高级搜索采集：按事件 + 三类切片关键词，取历史时间窗内的原帖。"""
import subprocess, json, base64, time, os, random, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'raw')
os.makedirs(RAW, exist_ok=True)

EVENTS = {
    '白海豚':      ('2026-08-08', '2026-08-30', '白海豚'),
    '杜苏芮':      ('2023-07-28', '2023-08-15', '杜苏芮'),
    '摩羯台风AI造假': ('2024-09-05', '2024-09-25', '摩羯 台风'),
}

SLICE_TERMS = {
    'A': ['真的假的', '求证实', '听说', '安置点', '断水断电'],
    'B': ['AI 造假', '造谣 拘留', '摆拍', '营销号', '严惩'],
    'C': ['辟谣 官方', '通报'],
}

JS_TPL = r"""
(async () => {
  const u = 'https://s.weibo.com/weibo?q=' + encodeURIComponent(%s)
          + '&typeall=1&suball=1&timescope=custom:%s:%s&page=%d';
  const r = await fetch(u, {credentials:'include'});
  const html = await r.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const cards = [...doc.querySelectorAll('div.card-wrap[action-type=feed_list_item]')];
  const rows = cards.map(c => {
    const full  = c.querySelector('p[node-type=feed_list_content_full]');
    const part  = c.querySelector('p[node-type=feed_list_content]');
    const txt   = ((full && full.textContent) || (part && part.textContent) || '').trim();
    const from  = c.querySelector('.from a');
    const act   = c.querySelector('.card-act');
    const stats = act ? act.innerText.replace(/\s+/g, ' ').trim() : '';
    return {
      mid:  c.getAttribute('mid'),
      user: (c.querySelector('.name') || {}).textContent ? c.querySelector('.name').textContent.trim() : '',
      time: from ? from.textContent.trim().replace(/\s+/g, ' ') : '',
      href: from ? from.getAttribute('href') : '',
      text: txt,
      stats: stats
    };
  });
  return JSON.stringify({status: r.status, n: cards.length, rows: rows});
})()
"""


def ev(js, timeout=90):
    b = base64.b64encode(js.encode('utf-8')).decode()
    p = subprocess.run(['agent-browser', 'eval', '-b', b],
                       capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or '').strip()
    if not out:
        return None, (p.stderr or 'empty')[:200]
    try:
        v = json.loads(out)
    except Exception:
        return None, out[:200]
    if isinstance(v, str):
        try:
            return json.loads(v), None
        except Exception:
            return v, None
    return v, None


def main():
    tasks = []
    for ev_name, (d1, d2, kw) in EVENTS.items():
        for sl, terms in SLICE_TERMS.items():
            for t in terms:
                tasks.append((ev_name, sl, kw + ' ' + t, d1, d2))

    print(f'共 {len(tasks)} 组检索式', flush=True)
    for ev_name, sl, q, d1, d2 in tasks:
        out_path = os.path.join(RAW, f'search_{ev_name}.jsonl')
        got_total = 0
        for page in range(1, 4):
            js = JS_TPL % (json.dumps(q, ensure_ascii=False), d1, d2, page)
            data, err = ev(js)
            if err or not isinstance(data, dict):
                print(f'  ! {ev_name} | {q} | p{page} 失败: {str(err)[:120]}', flush=True)
                time.sleep(8)
                continue
            rows = data.get('rows') or []
            if not rows:
                break
            got_total += len(rows)
            with open(out_path, 'a', encoding='utf-8') as f:
                for r in rows:
                    r.update(event=ev_name, slice_hint=sl, query=q,
                             date_from=d1, date_to=d2, page=page)
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            time.sleep(random.uniform(2.2, 4.0))
        print(f'  {ev_name:<10} [{sl}] {q:<22} -> {got_total} 条', flush=True)
        time.sleep(random.uniform(2.5, 4.5))


if __name__ == '__main__':
    main()
