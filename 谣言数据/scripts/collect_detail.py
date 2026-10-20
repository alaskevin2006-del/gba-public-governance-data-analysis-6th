#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 m.weibo.cn 同源上下文里：1) 补全每条博文的点赞量等互动数；2) 抓取媒体/官方热帖的评论。"""
import subprocess, json, base64, time, os, random, glob, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'raw')


def ev(js, timeout=180):
    b = base64.b64encode(js.encode('utf-8')).decode()
    p = subprocess.run(['agent-browser', 'eval', '-b', b],
                       capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or '').strip()
    if not out:
        return None, (p.stderr or 'empty')[:160]
    try:
        v = json.loads(out)
    except Exception:
        return None, out[:160]
    if isinstance(v, str):
        try:
            return json.loads(v), None
        except Exception:
            return v, None
    return v, None


JS_LIKES = r"""
(async () => {
  const ids = %s;
  const out = [];
  for (const o of ids) {
    try {
      const r = await fetch('https://m.weibo.cn/statuses/show?id=' + o.mblogid,
        {headers:{'MWeibo-Pwa':'1','X-Requested-With':'XMLHttpRequest'}});
      const j = await r.json();
      const d = j && j.data;
      out.push(d ? {mid:o.mid, ok:1,
            likes: d.attitudes_count|0, comments: d.comments_count|0,
            reposts: d.reposts_count|0, created_at: d.created_at,
            text: String(d.text||'').replace(/<[^>]+>/g,''),
            user: d.user ? d.user.screen_name : ''} : {mid:o.mid, ok:0});
    } catch(e) { out.push({mid:o.mid, ok:0}); }
    await new Promise(r => setTimeout(r, 260));
  }
  return JSON.stringify(out);
})()
"""

JS_COMMENTS = r"""
(async () => {
  const ids = %s;
  const out = [];
  for (const o of ids) {
    for (const page of [0,1]) {
      try {
        const u = 'https://m.weibo.cn/comments/hotflow?id=' + o.mid + '&mid=' + o.mid
                + '&max_id=' + (page ? o.maxid : 0) + '&max_id_type=0';
        const r = await fetch(u, {headers:{'MWeibo-Pwa':'1','X-Requested-With':'XMLHttpRequest',
          'Referer':'https://m.weibo.cn/status/' + o.mid}});
        const j = await r.json();
        const d = j && j.data;
        if (!d || !d.data) break;
        const maxid = d.max_id;
        for (const c of d.data) {
          out.push({comment_id: c.id, root_mid: o.mid, root_user: o.user,
            user: c.user ? c.user.screen_name : '', time: c.created_at,
            likes: c.like_counts|0,
            text: String(c.text||'').replace(/<[^>]+>/g,''),
            maxid: maxid, page: page});
        }
        if (page === 0) o.maxid = maxid;
        await new Promise(r => setTimeout(r, 320));
      } catch(e) { break; }
    }
    await new Promise(r => setTimeout(r, 260));
  }
  return JSON.stringify(out);
})()
"""


def mblogid_from_href(href):
    m = re.search(r'weibo\.com/\d+/([A-Za-z0-9]+)', href or '')
    return m.group(1) if m else None


def main():
    # ---------- 1. 汇总所有 mid ----------
    recs = {}
    for fp in glob.glob(os.path.join(RAW, 'search_*.jsonl')):
        for line in open(fp, encoding='utf-8'):
            r = json.loads(line)
            mid = r.get('mid')
            if mid and mid not in recs:
                recs[mid] = r
    print(f'唯一博文 {len(recs)} 条', flush=True)

    done_likes = set()
    lp = os.path.join(RAW, 'likes.jsonl')
    if os.path.exists(lp):
        for line in open(lp, encoding='utf-8'):
            x = json.loads(line)
            if x.get('ok'):
                done_likes.add(x['mid'])
    done_cmt = set()
    cp = os.path.join(RAW, 'comments.jsonl')
    if os.path.exists(cp):
        for line in open(cp, encoding='utf-8'):
            done_cmt.add(json.loads(line).get('root_mid'))

    items = []
    for mid, r in recs.items():
        if mid in done_likes:
            continue
        mb = mblogid_from_href(r.get('href', ''))
        items.append({'mid': mid, 'mblogid': mb})
    print(f'待补点赞 {len(items)} 条', flush=True)

    # ---------- 2. 点赞量补全 ----------
    like_out = []
    B = 18
    for i in range(0, len(items), B):
        batch = [x for x in items[i:i + B] if x.get('mblogid')]
        if not batch:
            continue
        data, err = ev(JS_LIKES % json.dumps(batch, ensure_ascii=False))
        if err or not isinstance(data, list):
            print(f'  ! 点赞批次 {i//B} 失败 {str(err)[:100]}', flush=True)
            time.sleep(10)
            continue
        like_out.extend(data)
        print(f'  点赞 {min(i+B, len(items))}/{len(items)}', flush=True)
        time.sleep(random.uniform(1.5, 2.5))

    with open(os.path.join(RAW, 'likes.jsonl'), 'a', encoding='utf-8') as f:
        for x in like_out:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')

    # ---------- 3. 切片C 媒体/官方热帖评论 ----------
    media_kw = ['日报', '新闻', '发布', '网警', '公安', '融媒', '电视台', '央视', '新华', '人民',
                '观察', '晚报', '时报', '广播', '宣传', '辟谣', '政府', '应急', '气象']
    cands = []
    for mid, r in recs.items():
        if mid in done_cmt:
            continue
        u = r.get('user', '')
        if r.get('slice_hint') == 'C' or any(k in u for k in media_kw):
            cands.append(r)
    # 每个事件取前 18 条媒体帖
    by_ev = {}
    for r in cands:
        by_ev.setdefault(r['event'], []).append(r)
    picked = []
    for e, lst in by_ev.items():
        lst.sort(key=lambda x: x['page'])
        picked.extend(lst[:18])
    print(f'待抓评论的媒体热帖 {len(picked)} 条', flush=True)

    cmt = []
    for i in range(0, len(picked), 4):
        batch = [{'mid': r['mid'], 'user': r.get('user', ''), 'maxid': 0}
                 for r in picked[i:i + 4]]
        data, err = ev(JS_COMMENTS % json.dumps(batch, ensure_ascii=False), timeout=240)
        if err or not isinstance(data, list):
            print(f'  ! 评论批次 {i//4} 失败 {str(err)[:100]}', flush=True)
            time.sleep(10)
            continue
        ev_name = picked[i]['event']
        for c in data:
            c['event'] = ev_name
        cmt.extend(data)
        print(f'  评论 {min(i+4, len(picked))}/{len(picked)} 累计 {len(cmt)}', flush=True)
        time.sleep(random.uniform(1.5, 2.5))

    with open(os.path.join(RAW, 'comments.jsonl'), 'a', encoding='utf-8') as f:
        for c in cmt:
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    print(f'完成：点赞 {len(like_out)}，评论 {len(cmt)}', flush=True)


if __name__ == '__main__':
    main()
