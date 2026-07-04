#!/usr/bin/env python3
"""
豆瓣电影日历爬虫 + Kindle适配HTML生成器
豆列: https://www.douban.com/doulist/162625203/
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import os

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://www.douban.com/',
}

BASE_URL = 'https://www.douban.com/doulist/162625203/'


def parse_item(item_div):
    """解析单个 doulist-item，返回 dict"""
    data = {}

    # --- 电影名 ---
    title_div = item_div.find('div', class_='title')
    if title_div:
        a_tag = title_div.find('a')
        if a_tag:
            # 去掉 img 图标，只取文本
            if a_tag.img:
                a_tag.img.decompose()
            data['title'] = a_tag.get_text(strip=True)
            data['url'] = a_tag.get('href', '')

    # --- 评分 ---
    rating_div = item_div.find('div', class_='rating')
    if rating_div:
        nums_span = rating_div.find('span', class_='rating_nums')
        if nums_span:
            data['rating'] = nums_span.get_text(strip=True)
        # allstar class e.g. allstar45 -> 4.5 stars -> 9/10 * 5... let's convert
        allstar_span = rating_div.find('span', class_=re.compile(r'allstar\d+'))
        if allstar_span:
            cls = allstar_span.get('class', [''])[0]
            m = re.search(r'allstar(\d+)', cls)
            if m:
                star_val = int(m.group(1)) / 10  # allstar45 -> 4.5
                data['star'] = star_val

    # --- 简介（导演/主演/类型/年份） ---
    abstract_div = item_div.find('div', class_='abstract')
    if abstract_div:
        # Replace <br/> with newline, then split
        text = abstract_div.get_text('\n', strip=True)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in lines:
            if line.startswith('导演:'):
                data['director'] = line.replace('导演:', '').strip()
            elif line.startswith('主演:'):
                data['actors'] = line.replace('主演:', '').strip()
            elif line.startswith('类型:'):
                data['genre'] = line.replace('类型:', '').strip()
            elif line.startswith('制片国家/地区:'):
                data['country'] = line.replace('制片国家/地区:', '').strip()
            elif line.startswith('年份:'):
                data['year'] = line.replace('年份:', '').strip()
            else:
                # try to match "年份: 2024" without prefix
                ym = re.match(r'(\d{4})$', line)
                if ym:
                    data['year'] = ym.group(1)

    # --- 海报 ---
    post_div = item_div.find('div', class_='post')
    if post_div:
        img = post_div.find('img')
        if img:
            src = img.get('src', '')
            if src:
                data['poster'] = src

    # --- 评论（日期 + 台词） ---
    comment_div = item_div.find('div', class_='comment-item')
    if comment_div:
        blockquote = comment_div.find('blockquote', class_='comment')
        if blockquote:
            comment_text = blockquote.get_text(strip=True)
            # Remove "评语：" prefix
            comment_text = re.sub(r'^评语[：:]', '', comment_text).strip()
            # Try to extract date at the beginning: e.g. "1月1日 我觉得..."
            # or "1月1日" then content
            date_match = re.match(r'(\d{1,2})月(\d{1,2})日[，\s]*(.*)', comment_text)
            if date_match:
                data['month'] = int(date_match.group(1))
                data['day'] = int(date_match.group(2))
                data['quote'] = date_match.group(3).strip()
            else:
                # Maybe just "1月1日" without following text
                date_match2 = re.match(r'(\d{1,2})月(\d{1,2})日', comment_text)
                if date_match2:
                    data['month'] = int(date_match2.group(1))
                    data['day'] = int(date_match2.group(2))
                    rest = comment_text[date_match2.end():].strip()
                    data['quote'] = rest if rest else ''
                else:
                    data['quote'] = comment_text

    return data


def fetch_page(start=0):
    """抓取一页数据"""
    params = {'start': start, 'sort': 'time', 'sub_type': 2}
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.encoding = 'utf-8'
    resp.raise_for_status()
    return resp.text


def scrape_all():
    """抓取全部15页"""
    all_items = []
    for page in range(15):
        start = page * 25
        print(f"  抓取第 {page+1}/15 页 (start={start})...")
        html = fetch_page(start)
        soup = BeautifulSoup(html, 'html.parser')
        item_divs = soup.find_all('div', class_='doulist-item')
        print(f"    找到 {len(item_divs)} 个条目")
        for item_div in item_divs:
            data = parse_item(item_div)
            if data.get('title') and data.get('month'):
                all_items.append(data)
        # 礼貌性延迟
        if page < 14:
            time.sleep(1.5)
    return all_items


def sort_items(items):
    """按月、日排序"""
    return sorted(items, key=lambda x: (x.get('month', 0), x.get('day', 0)))


def generate_html(items, output_path):
    """生成 Kindle Paperwhite 10代 适配的 HTML 日历页面"""
    items = sort_items(items)

    month_names = ['', '一月', '二月', '三月', '四月', '五月', '六月',
                  '七月', '八月', '九月', '十月', '十一月', '十二月']

    # Build HTML
    html_parts = []
    html_parts.append('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=2.0">
<title>2026年豆瓣电影日历</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #fff;
    color: #000;
    padding: 24px 20px 48px;
    max-width: 800px;
    margin: 0 auto;
    line-height: 1.7;
  }

  /* ===== 标题区 ===== */
  h1 {
    text-align: center;
    font-size: 26px;
    font-weight: 700;
    padding: 24px 0 6px;
    letter-spacing: 3px;
  }
  .subtitle {
    text-align: center;
    font-size: 14px;
    color: #555;
    margin-bottom: 20px;
    padding-bottom: 14px;
    border-bottom: 1px solid #ccc;
  }

  /* ===== 月份导航 ===== */
  .month-nav {
    text-align: center;
    margin: 16px 0 20px;
    padding: 10px 0;
    border-top: 1px solid #ccc;
    border-bottom: 1px solid #ccc;
  }
  .month-nav a {
    display: inline-block;
    margin: 3px 5px;
    padding: 4px 8px;
    font-size: 13px;
    font-weight: 600;
    color: #000;
    text-decoration: none;
    border: 1px solid #999;
  }
  .month-nav a:hover { background: #eee; }

  /* ===== 月份标题 ===== */
  .month-header {
    font-size: 22px;
    font-weight: 700;
    padding: 22px 0 8px;
    margin: 10px 0 14px;
    border-bottom: 3px solid #000;
    letter-spacing: 2px;
  }

  /* ===== 每日条目标签 ===== */
  .day-card {
    display: flex;
    gap: 14px;
    padding: 14px 0;
    border-bottom: 1px solid #ddd;
  }
  /* 今天：加粗外框 + 灰底反转 */
  .day-card.today {
    background: #111;
    color: #fff;
    margin: 6px -6px;
    padding: 14px 10px;
    border: 2px solid #000;
  }
  .day-card.today a { color: #ddd; }

  /* 左侧：日期数字 + 周几 */
  .day-left {
    flex: 0 0 60px;
    text-align: center;
  }
  .day-left .day-num {
    font-size: 34px;
    font-weight: 700;
    line-height: 1.0;
    color: #000;
  }
  .day-left .day-week {
    font-size: 12px;
    color: #666;
    margin-top: 3px;
  }
  .day-card.today .day-left .day-num { color: #fff; }
  .day-card.today .day-left .day-week { color: #ccc; }

  /* 右侧：电影信息 */
  .day-right { flex: 1; min-width: 0; }

  .movie-title {
    font-size: 17px;
    font-weight: 600;
    margin-bottom: 4px;
  }
  .movie-title a {
    color: #000;
    text-decoration: none;
    border-bottom: 1px dotted #aaa;
  }
  .day-card.today .movie-title a { color: #ddd; border-color: #888; }

  .movie-meta {
    font-size: 13px;
    color: #555;
    margin-bottom: 6px;
  }
  .movie-meta .rating-star { font-weight: 700; }

  /* 经典台词 */
  .movie-quote {
    font-size: 14px;
    font-style: italic;
    line-height: 1.6;
    padding: 6px 10px;
    margin-top: 4px;
    border-left: 3px solid #999;
    color: #333;
  }
  .day-card.today .movie-quote {
    color: #ccc;
    border-left-color: #888;
  }

  /* 底部 */
  .footer {
    text-align: center;
    font-size: 12px;
    color: #888;
    padding: 32px 0 16px;
    border-top: 1px solid #ccc;
    margin-top: 24px;
  }

  /* E-Ink / Kindle 专项优化 */
  @media (max-width: 500px) {
    body { padding: 14px 12px 32px; }
    .day-left { flex-basis: 50px; }
    .day-left .day-num { font-size: 28px; }
    .movie-title { font-size: 15px; }
    .movie-quote { font-size: 13px; }
  }
  @media print {
    body { background: #fff; }
    .day-card { break-inside: avoid; }
    .month-nav { display: none; }
  }
</style>
</head>
<body>
''')

    # Header
    html_parts.append('<h1>2026 豆瓣电影日历</h1>\n')
    html_parts.append('<p class="subtitle">每天一部好电影</p>\n')

    # Month navigation links
    html_parts.append('<div class="month-nav">\n')
    for m in range(1, 13):
        html_parts.append(f'<a href="#month{m}">{month_names[m]}</a>\n')
    html_parts.append('</div>\n')

    # Weekday mapping for 2026
    # 2026-01-01 is Thursday (周四)
    import datetime
    base_date = datetime.date(2026, 1, 1)
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

    # Group by month
    current_month = 0
    for item in items:
        m = item.get('month', 0)
        d = item.get('day', 0)

        # Month header
        if m != current_month:
            current_month = m
            month_names = ['', '一月', '二月', '三月', '四月', '五月', '六月',
                          '七月', '八月', '九月', '十月', '十一月', '十二月']
            html_parts.append(f'<div class="month-header" id="month{m}">{month_names[m]}</div>\n')

        # Check if today
        year = 2026
        try:
            this_date = datetime.date(year, m, d)
        except ValueError:
            this_date = None
        weekday_idx = this_date.weekday() if this_date else 0
        today_str = datetime.date.today().strftime('%Y-%m-%d')

        is_today = (this_date and this_date.strftime('%Y-%m-%d') == today_str)
        card_class = 'day-card today' if is_today else 'day-card'

        week_str = weekday_names[weekday_idx] if this_date else ''

        # Quote
        quote = item.get('quote', '')
        quote_html = f'<div class="movie-quote">“{quote}”</div>' if quote else ''

        # Rating display
        rating = item.get('rating', '')
        star = item.get('star', 0)
        star_str = f'★{int(star)}' if star else ''
        rating_display = f'{rating} {star_str}' if rating else '暂无评分'

        # Title with link
        title = item.get('title', '未知')
        url = item.get('url', '')
        title_html = f'<a href="{url}">{title}</a>' if url else title

        # Meta info
        meta_parts = []
        meta_parts.append(f'<span class="rating-star">{rating_display}</span>')
        if item.get('director'):
            meta_parts.append(item['director'])
        if item.get('year'):
            meta_parts.append(item['year'])
        meta_str = ' · '.join(meta_parts)

        html_parts.append(f'''<div class="{card_class}">
  <div class="day-left">
    <div class="day-num">{d}</div>
    <div class="day-week">{week_str}</div>
  </div>
  <div class="day-right">
    <div class="movie-title">{title_html}</div>
    <div class="movie-meta">{meta_str}</div>
    {quote_html}
  </div>
</div>
''')

    # Footer
    html_parts.append('<div class="footer">数据来源：豆瓣 · 豆列 #162625203<br>生成于 {}</div>\n'.format(
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    ))
    html_parts.append('</body>\n</html>')

    html_content = ''.join(html_parts)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return output_path


def verify_html(output_path):
    """简单验证 HTML 文件"""
    with open(output_path, 'r', encoding='utf-8') as f:
        content = f.read()
    stats = {
        '文件大小(KB)': round(len(content) / 1024, 1),
        '条目数': content.count('class="day-card'),
        '月份数': content.count('class="month-header'),
        '包含海报': 'poster' in content,
    }
    return stats


def main():
    print("=" * 50)
    print("豆瓣电影日历爬虫 + HTML 生成器")
    print("豆列: https://www.douban.com/doulist/162625203/")
    print("=" * 50)

    # Step 1: scrape
    print("\n[1/3] 开始爬取数据...")
    items = scrape_all()
    print(f"\n  共爬取 {len(items)} 条有效数据")

    # Step 2: sort
    items = sort_items(items)

    # Sample check
    print("\n  数据样例（前3条）:")
    for item in items[:3]:
        print(f"    {item.get('month')}月{item.get('day')}日 | {item.get('title')} | "
              f"评分:{item.get('rating','')} | 台词: {item.get('quote','')[:30]}...")

    # Step 3: generate HTML
    print("\n[2/3] 生成 HTML 页面...")
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'douban_calendar_2026.html')
    result = generate_html(items, output_path)
    print(f"  HTML 已生成: {output_path}")

    # Step 4: verify
    print("\n[3/3] 验证输出...")
    stats = verify_html(output_path)
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n✅ 完成！")
    print(f"📁 HTML 文件: {output_path}")
    print("💡 用法: 将 HTML 文件拷贝到 Kindle 的 documents 目录，")
    print("   然后用 Kindle 浏览器打开即可。")


if __name__ == '__main__':
    main()
