#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清洗 + 打标 + 分事件导出 CSV + 生成采集日志。"""
import json, os, re, glob, csv, math
from datetime import datetime, timedelta
from opencc import OpenCC

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'raw')
DATA = os.path.join(BASE, 'data')
os.makedirs(DATA, exist_ok=True)

CC = OpenCC('t2s')
NOW = datetime(2026, 10, 20, 12, 0)
CRAWL_TIME = '2026-10-20 12:20'

EVENTS = ['白海豚', '杜苏芮', '摩羯台风AI造假']
EVENT_LABEL = {'白海豚': '白海豚', '杜苏芮': '杜苏芮', '摩羯台风AI造假': '摩羯台风谣言和ai造假事件'}

# 事件相关性硬约束（防止“摩羯座”、中华白海豚等噪声混入）
RELEV = {
    '白海豚': re.compile(r'白海豚'),
    '杜苏芮': re.compile(r'杜苏芮'),
    '摩羯台风AI造假': re.compile(r'摩羯'),
}
NEG = {
    '白海豚': re.compile(r'中华白海豚|三娘湾|钦州|湛江.*白海豚保护区'),
    '摩羯台风AI造假': re.compile(r'摩羯座|摩羯男|摩羯女|星座|运势|上升摩羯'),
}

def abs_url(href):
    if not href:
        return ''
    return 'https://' + href.lstrip('/').split('?')[0]


URL_RE = re.compile(r'(https?://\S+|www\.\S+|t\.cn/\S+|O网页链接|网页链接)')
AT_RE = re.compile(r'@[\w\u4e00-\u9fa5\-\.]{1,30}')
TAG_RE = re.compile(r'#([^#\n]{1,40})#')
EMOJI_RE = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d\u2B00-\u2BFF]')
CTRL_RE = re.compile(r'[\s\u200b\u200c\u200d]+')
AD_RE = re.compile(r'加微信|加V信|加v信|私信我|代购|优惠券|领取红包|兼职刷单|招代理|扫码进群|wx[:：]|vx[:：]|引流带货')
OFFICIAL_RE = re.compile(r'谣|辟谣|警方|公安|通报|处罚|查处|拘留|行拘|违法|打击|网信')
ZH_RE = re.compile(r'[\u4e00-\u9fa5]')

MEDIA_KW = ['日报', '新闻', '发布', '网警', '公安', '融媒', '电视台', '央视', '新华', '人民',
            '观察', '晚报', '时报', '广播', '宣传', '辟谣', '政府', '应急', '气象', '网信', '政法']
A_SIG = re.compile(r'真的假的|假的吧|求证实|求证|有没有事|听说|是不是真的|真的吗|不敢信|求真相|怎么回事|真的假的啊|是真的么|真假')
B_STRONG = re.compile(r'AI生成|ai生成|AI造假|ai造假|人工智能生成|假视频|合成视频|P图|p图|摆拍|造假|拘留|行拘|刑拘|严惩|追责|营销号|带节奏|离谱|移花接木')
B_SIG = re.compile(r'AI|ai|造谣|谣言|处罚|辟谣|通报|回应|不实|官方|警方|查处|整治|反思|底线|流量|蹭热点')
A_PANIC = re.compile(r'没饭吃|断水断电|停水停电|被困|失联|楼塌|塌了|淹了|物资|救援|伤亡|死了|被困|难民营|安置点')

COMMENT_TYPES = {
    '切片A_求证恐慌型': 'A',
    '切片B_争议反思谴责型': 'B',
    '切片C_媒体热帖评论': 'C',
}


def parse_time(s, ref=NOW):
    if not s:
        return None
    s = str(s).strip()
    # m.weibo.cn 的 created_at：Tue Oct 20 11:26:01 +0800 2026
    if re.match(r'^[A-Z][a-z]{2} [A-Z][a-z]{2} ', s):
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(s).replace(tzinfo=None)
        except Exception:
            pass
    s = s.replace('今天', datetime.now().strftime('%Y年%m月%d日')).replace('昨天', '')
    m = re.search(r'(\d{4})年(\d{2})月(\d{2})日\s*(\d{2}):(\d{2})', s)
    if m:
        return datetime(*map(int, m.groups()))
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', s)
    if m:
        return datetime(*map(int, m.groups()))
    m = re.search(r'(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})', s)
    if m:
        mo, d, hh, mm = map(int, m.groups())
        return datetime(2026 if mo >= 8 else 2025, mo, d, hh, mm)
    m = re.search(r'(\d+)\s*分钟前', s)
    if m:
        return NOW - timedelta(minutes=int(m.group(1)))
    m = re.search(r'(\d+)\s*小时前', s)
    if m:
        return NOW - timedelta(hours=int(m.group(1)))
    return None


def clean_text(t):
    if not t:
        return ''
    t = str(t)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = t.replace('&nbsp;', ' ').replace('&amp;', '&')
    t = CC.convert(t)                       # 繁体 -> 简体
    t = URL_RE.sub(' ', t)                  # 去 URL
    t = AT_RE.sub(' ', t)                   # 去 @用户名
    t = TAG_RE.sub(r'\1', t)                # 去话题符号，保留话题内文字
    t = t.replace('展开', ' ').replace('收起', ' ')
    t = EMOJI_RE.sub(' ', t)                # 去表情
    t = CTRL_RE.sub(' ', t)
    t = re.sub(r'[“”"\'’‘]', '', t)
    t = re.sub(r'^(转发微博|轉發微博|Repost)$', '', t)
    return t.strip(' ，。、,.;；:：/\\|-_')


def is_noise(t):
    if not t:
        return '空白'
    if len(ZH_RE.findall(t)) < 2:
        return '少于2个汉字'
    if len(ZH_RE.findall(t)) <= 3 and not re.search(r'台风|暴雨|洪|水|电|雨|谣|AI|楼|车|救援|物资', t):
        return '信息量过低'
    if AD_RE.search(t) and not OFFICIAL_RE.search(t):
        return '广告导流'
    if re.fullmatch(r'[哈啊哦嗯呀噢嘿额\-—\s]{2,}', t):
        return '无意义语气词'
    return None


def load_raw():
    posts, seen = [], {}
    for fp in glob.glob(os.path.join(RAW, 'search_*.jsonl')):
        for line in open(fp, encoding='utf-8'):
            r = json.loads(line)
            key = r.get('mid')
            if key in seen:
                seen[key]['qev'].setdefault(r['event'], [])
                if r.get('query') not in seen[key]['qev'][r['event']]:
                    seen[key]['qev'][r['event']].append(r.get('query'))
                continue
            r['queries'] = [r.get('query')]
            r['qev'] = {r['event']: [r.get('query')]}
            seen[key] = r
            posts.append(r)
    return posts


def load_likes():
    d = {}
    fp = os.path.join(RAW, 'likes.jsonl')
    if os.path.exists(fp):
        for line in open(fp, encoding='utf-8'):
            x = json.loads(line)
            if x.get('ok'):
                d[x['mid']] = x
    return d


def load_comments():
    fp = os.path.join(RAW, 'comments.jsonl')
    out = []
    if os.path.exists(fp):
        for line in open(fp, encoding='utf-8'):
            out.append(json.loads(line))
    return out


def classify(text, user, hint, source):
    if source == 'comment':
        return '切片C_媒体热帖评论'
    is_media = any(k in (user or '') for k in MEDIA_KW)
    if is_media and (re.search(r'辟谣|通报|回应|不实|谣言|提醒', text) or hint == 'C'):
        return '切片C_媒体热帖评论'
    if B_STRONG.search(text):
        return '切片B_争议反思谴责型'
    if A_SIG.search(text):
        return '切片A_求证恐慌型'
    if B_SIG.search(text):
        return '切片B_争议反思谴责型'
    return {'A': '切片A_求证恐慌型', 'B': '切片B_争议反思谴责型', 'C': '切片C_媒体热帖评论'}[hint]


def main():
    posts = load_raw()
    likes = load_likes()
    comments = load_comments()
    print(f'原始博文 {len(posts)}（去重后），评论 {len(comments)}')

    rows = []          # 全部候选
    valid_mids = {}    # event -> 通过相关性与清洗的博文 mid
    drop_log = {}      # event -> {原因: 数量}

    def drop(e, reason):
        drop_log.setdefault(e, {}).setdefault(reason, 0)
        drop_log[e][reason] += 1

    # ---- 博文 ----
    for p in posts:
        e = p['event']
        raw_txt = p.get('text', '') or ''
        if RELEV[e].search(raw_txt) is None:
            # 媒体/政务辟谣类热帖常把灾种写在正文而不重复事件名，放宽一类
            allow_c = (p.get('slice_hint') == 'C'
                       and re.search(r'台风|汛|暴雨|洪水', raw_txt)
                       and re.search(r'谣|辟谣|不实|AI|造假|假图|假视频', raw_txt))
            if not allow_c:
                drop(e, '事件无关')
                continue
        if e in NEG and NEG[e].search(raw_txt):
            drop(e, '同名噪声')
            continue
        c = clean_text(raw_txt)
        n = is_noise(c)
        if n:
            drop(e, n)
            continue
        lk = likes.get(p['mid'], {})
        valid_mids.setdefault(e, set()).add(str(p['mid']))
        rows.append({
            'id': p['mid'],
            'event': e,
            'slice': classify(c, p.get('user', ''), p.get('slice_hint', 'A'), 'post'),
            'user': p.get('user', ''),
            'time': parse_time(p.get('time', '')),
            'time_raw': p.get('time', ''),
            'likes': lk.get('likes', ''),
            'raw': raw_txt,
            'clean': c,
            'url': abs_url(p.get('href')),
            'query': '；'.join(dict.fromkeys(p['qev'].get(e, []))),
            'qlist': list(dict.fromkeys(p['qev'].get(e, []))),
            'source': '博文',
        })

    # ---- 评论（必须挂在有效博文之下，避免检索式失真带出的无关评论）----
    for c0 in comments:
        e = c0.get('event')
        if str(c0.get('root_mid')) not in valid_mids.get(e, set()):
            drop(e, '母帖无效')
            continue
        raw_txt = c0.get('text', '') or ''
        c = clean_text(raw_txt)
        n = is_noise(c)
        if n:
            drop(e, n)
            continue
        rows.append({
            'id': c0.get('comment_id'),
            'event': e,
            'slice': '切片C_媒体热帖评论',
            'user': c0.get('user', ''),
            'time': parse_time(c0.get('time', '')),
            'time_raw': c0.get('time', ''),
            'likes': c0.get('likes', 0),
            'raw': raw_txt,
            'clean': c,
            'url': 'https://weibo.com/' + str(c0.get('root_mid')),
            'query': '切片C-媒体热帖评论',
            'source': '评论',
        })

    # ---- 去重：同用户同文本，其次跨账号完全相同文本 ----
    for e in EVENTS:
        sub = [r for r in rows if r['event'] == e]
        seen_user, seen_text, keep = set(), set(), []
        for r in sub:
            k1 = (r['user'], r['clean'])
            if k1 in seen_user:
                drop(e, '同用户重复')
                continue
            seen_user.add(k1)
            k2 = r['clean']
            if k2 in seen_text:
                drop(e, '跨账号重复文本')
                continue
            seen_text.add(k2)
            keep.append(r)
        rows = [r for r in rows if r['event'] != e] + keep

    # ---- 导出 ----
    FIELDS = ['id', '事件标签', '切片类型', '发布账号', '发布时间', '点赞量', '原文文本', '清洗后文本']
    detail_fields = ['id', '事件标签', '切片类型', '来源类型', '发布账号', '发布时间', '点赞量',
                     '原文文本', '清洗后文本', '博文链接', '命中检索词']
    detail_all = []

    stats = {}
    for e in EVENTS:
        sub = sorted([r for r in rows if r['event'] == e],
                     key=lambda x: (x['time'] or datetime(1970, 1, 1)))
        fp = os.path.join(DATA, f'{e}_谣言数据集.csv')
        with open(fp, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(FIELDS)
            for r in sub:
                w.writerow([r['id'], EVENT_LABEL[e], r['slice'], r['user'],
                            r['time'].strftime('%Y-%m-%d %H:%M') if r['time'] else r['time_raw'],
                            r['likes'], r['raw'], r['clean']])
        for r in sub:
            detail_all.append([r['id'], EVENT_LABEL[e], r['slice'], r['source'], r['user'],
                               r['time'].strftime('%Y-%m-%d %H:%M') if r['time'] else r['time_raw'],
                               r['likes'], r['raw'], r['clean'], r['url'], r['query']])
        times = [r['time'] for r in sub if r['time']]
        stats[e] = {
            'valid': len(sub),
            'span': (min(times), max(times)) if times else (None, None),
            'slice': {s: sum(1 for r in sub if r['slice'] == s) for s in COMMENT_TYPES},
        }
        print(f'{e}: 有效 {len(sub)} 条')

    with open(os.path.join(DATA, '全量明细_含链接.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(detail_fields)
        w.writerows(detail_all)

    # ---- 采集日志 ----
    log_fields = ['事件标签', '切片类型', '检索词', '检索时间窗', '抓取时间',
                  '抓取原始条数', '清洗剔除数', '有效样本量', '博文链接（示例）']
    with open(os.path.join(DATA, '采集日志.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(log_fields)
        for e in EVENTS:
            qmap = {}
            for p in posts:
                for q in p.get('qev', {}).get(e, []):
                    if not q:
                        continue
                    qmap.setdefault(q, {'n': 0, 'links': [], 'win': f"{p['date_from']} 至 {p['date_to']}"})
                    qmap[q]['n'] += 1
                    if p.get('href') and len(qmap[q]['links']) < 3:
                        qmap[q]['links'].append(abs_url(p['href']))
            for q, v in qmap.items():
                sl = classify(q, '', 'A', 'post')
                sub = [r for r in rows if r['event'] == e]
                kept = sum(1 for r in sub if q in r.get('qlist', []))
                w.writerow([EVENT_LABEL[e], sl, q, v['win'], CRAWL_TIME,
                            v['n'], max(v['n'] - kept, 0), kept, ' | '.join(v['links'])])
            w.writerow([EVENT_LABEL[e], '合计', '—', '—', CRAWL_TIME,
                        stats[e]['valid'] + sum(drop_log.get(e, {}).values()),
                        sum(drop_log.get(e, {}).values()), stats[e]['valid'],
                        '见《全量明细_含链接.csv》'])

    json.dump({'stats': {k: {'valid': v['valid'],
                             'span': [t.strftime('%Y-%m-%d') if t else None for t in v['span']],
                             'slice': v['slice']} for k, v in stats.items()},
               'drop': drop_log,
               'raw_posts': len(posts), 'raw_comments': len(comments)},
              open(os.path.join(RAW, 'stats.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(drop_log, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
