#!/usr/bin/env python3
"""
豆瓣电影日历 - Kindle桌面日历面板版
每天一页大卡片，适合Kindle横屏/竖屏作为桌面日历使用
"""

import requests
from bs4 import BeautifulSoup
import re, time, os, json, base64
import datetime
import lunardate

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
BASE_URL = 'https://www.douban.com/doulist/162625203/'

WEEKDAY_CN = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
LUNAR_MONTH = ['', '正月', '二月', '三月', '四月', '五月', '六月',
               '七月', '八月', '九月', '十月', '冬月', '腊月']
LUNAR_DAY = ['', '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
             '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
             '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十']
TIANGAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
DIZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
SHENGXIAO = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪']


def parse_item(item_div):
    """解析单个 doulist-item"""
    data = {}
    title_div = item_div.find('div', class_='title')
    if title_div:
        a_tag = title_div.find('a')
        if a_tag:
            if a_tag.img:
                a_tag.img.decompose()
            data['title'] = a_tag.get_text(strip=True)
            data['url'] = a_tag.get('href', '')

    rating_div = item_div.find('div', class_='rating')
    if rating_div:
        nums_span = rating_div.find('span', class_='rating_nums')
        if nums_span:
            data['rating'] = nums_span.get_text(strip=True)
        allstar_span = rating_div.find('span', class_=re.compile(r'allstar\d+'))
        if allstar_span:
            cls = allstar_span.get('class', [''])[0]
            m = re.search(r'allstar(\d+)', cls)
            if m:
                data['star'] = float(m.group(1)) / 10

    abstract_div = item_div.find('div', class_='abstract')
    if abstract_div:
        text = abstract_div.get_text('\n', strip=True)
        for line in [l.strip() for l in text.split('\n') if l.strip()]:
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

    post_div = item_div.find('div', class_='post')
    if post_div:
        img = post_div.find('img')
        if img and img.get('src'):
            data['poster'] = img['src']

    comment_div = item_div.find('div', class_='comment-item')
    if comment_div:
        bq = comment_div.find('blockquote', class_='comment')
        if bq:
            text = re.sub(r'^评语[：:]', '', bq.get_text(strip=True)).strip()
            m = re.match(r'(\d{1,2})月(\d{1,2})日[，\s]*(.*)', text)
            if m:
                data['month'] = int(m.group(1))
                data['day'] = int(m.group(2))
                data['quote'] = m.group(3).strip()
            else:
                m2 = re.match(r'(\d{1,2})月(\d{1,2})日', text)
                if m2:
                    data['month'] = int(m2.group(1))
                    data['day'] = int(m2.group(2))
                    data['quote'] = text[m2.end():].strip()
    return data


def scrape_all():
    """抓取全部15页"""
    all_items = []
    for page in range(15):
        start = page * 25
        print(f"  抓取第 {page+1}/15 页...")
        resp = requests.get(BASE_URL, params={
            'start': start, 'sort': 'time', 'sub_type': 2
        }, headers=HEADERS, timeout=30)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        for item_div in soup.find_all('div', class_='doulist-item'):
            data = parse_item(item_div)
            if data.get('title') and data.get('month'):
                all_items.append(data)
        if page < 14:
            time.sleep(1.5)
    return sorted(all_items, key=lambda x: (x['month'], x['day']))


def get_lunar_str(year, month, day):
    """获取农历日期字符串"""
    try:
        l = lunardate.LunarDate.fromSolarDate(year, month, day)
        ym = l.year
        shengxiao = SHENGXIAO[(ym - 4) % 12]
        tiangan = TIANGAN[(ym - 4) % 10]
        dizhi = DIZHI[(ym - 4) % 12]
        month_str = LUNAR_MONTH[l.month] if l.month <= 12 else f'{l.month}月'
        day_str = LUNAR_DAY[l.day] if l.day <= 30 else f'{l.day}日'
        return f'{tiangan}{dizhi}{shengxiao}年 {month_str}{day_str}'
    except:
        return ''


def poster_to_data_uri(url):
    """把海报图片下载并转成 base64 data URI（方便Kindle离线显示）"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            ext = url.rsplit('.', 1)[-1].split('?')[0].lower()
            mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png'
            b64 = base64.b64encode(resp.content).decode()
            return f'data:{mime};base64,{b64}'
    except:
        pass
    return url  # fallback to original URL


def generate_calendar_html(items, output_path, embed_images=True):
    """生成日历面板HTML"""
    # 按日期索引
    day_map = {}
    for item in items:
        key = f"{item['month']:02d}{item['day']:02d}"
        day_map[key] = item

    # 生成所有条目的 JSON 数据
    entries = []
    print("  下载海报并生成 data URI...")
    for i, item in enumerate(items):
        poster = ''
        if embed_images and item.get('poster'):
            poster = poster_to_data_uri(item['poster'])
            if i % 20 == 0:
                print(f"    {i+1}/{len(items)}")
        entry = {
            'm': item['month'],
            'd': item['day'],
            't': item.get('title', ''),
            'q': item.get('quote', ''),
            'r': item.get('rating', ''),
            's': item.get('star', 0),
            'dir': item.get('director', ''),
            'act': item.get('actors', ''),
            'gen': item.get('genre', ''),
            'year': item.get('year', ''),
            'poster': poster,
            'url': item.get('url', ''),
            'lunar': item.get('lunar', ''),
        }
        entries.append(entry)

    data_json = json.dumps(entries, ensure_ascii=False)

    # 构建单页HTML
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>2026 豆瓣电影日历</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #fff;
    color: #000;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  /* ===== 顶部栏 ===== */
  .top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 16px;
    border-bottom: 1px solid #ccc;
    font-size: 14px;
    flex: 0 0 auto;
  }
  .top-bar .title { font-weight: 700; font-size: 16px; letter-spacing: 1px; }
  .top-bar .time { font-weight: 600; font-size: 15px; }
  .top-bar .battery { font-size: 12px; color: #666; }

  /* ===== 主内容区 ===== */
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 12px 16px;
    overflow: hidden;
    position: relative;
  }

  /* ===== 日期行 ===== */
  .date-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding-bottom: 8px;
    border-bottom: 2px solid #000;
    flex: 0 0 auto;
  }
  .date-left {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }
  .date-left .day-big {
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
  }
  .date-left .date-suffix {
    font-size: 16px;
    font-weight: 600;
    color: #555;
  }
  .date-right {
    text-align: right;
    font-size: 12px;
    color: #555;
    line-height: 1.4;
  }
  .date-right .lunar { font-size: 13px; }

  /* ===== 内容行（电影区） ===== */
  .content-row {
    flex: 1;
    display: flex;
    gap: 16px;
    padding-top: 10px;
    min-height: 0;
  }

  /* 左侧海报区 */
  .poster-area {
    flex: 0 0 35%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .poster-area img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border: 1px solid #ddd;
  }
  .poster-area .no-poster {
    width: 100%;
    height: 80%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f0f0f0;
    border: 1px solid #ddd;
    font-size: 13px;
    color: #999;
    text-align: center;
    padding: 10px;
  }

  /* 右侧信息区 */
  .info-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-width: 0;
  }
  .movie-title {
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 4px;
    line-height: 1.3;
  }
  .movie-title a { color: #000; text-decoration: none; }

  .movie-meta {
    font-size: 13px;
    color: #666;
    margin-bottom: 4px;
    line-height: 1.5;
  }
  .movie-meta .stars { font-weight: 700; color: #000; }

  .quote-area {
    margin-top: 8px;
    padding: 8px 10px;
    border-left: 3px solid #999;
    font-size: 14px;
    font-style: italic;
    line-height: 1.6;
    color: #333;
    background: #fafafa;
    flex: 1;
    display: flex;
    align-items: center;
    max-height: 50%;
    overflow: hidden;
  }

  /* ===== 底部导航 ===== */
  .nav-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 16px;
    border-top: 1px solid #ccc;
    flex: 0 0 auto;
  }
  .nav-btn {
    font-size: 22px;
    font-weight: 700;
    padding: 4px 16px;
    border: 1px solid #999;
    background: #fff;
    color: #000;
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
    min-width: 48px;
    text-align: center;
  }
  .nav-btn:active { background: #ddd; }
  .nav-btn.disabled { opacity: 0.3; }

  .nav-date {
    font-size: 13px;
    color: #555;
    text-align: center;
  }
  .nav-date .goto-input {
    width: 60px;
    text-align: center;
    border: 1px solid #ccc;
    font-size: 13px;
    padding: 2px 4px;
  }

  /* 竖屏适配 */
  @media (orientation: portrait) {
    .content-row { flex-direction: column; }
    .poster-area { flex: 0 0 auto; max-height: 40%; }
    .poster-area img { max-height: 100%; }
    .quote-area { max-height: 30%; }
  }
</style>
</head>
<body>

<div class="top-bar">
  <span class="title">2026 豆瓣电影日历</span>
  <span class="time" id="clockDisplay"></span>
  <span class="battery" id="batteryDisplay"></span>
</div>

<div class="main" id="mainContent">
  <div class="date-row" id="dateRow">
    <div class="date-left">
      <span class="day-big" id="dayBig"></span>
      <span class="date-suffix" id="dateSuffix"></span>
    </div>
    <div class="date-right">
      <div class="lunar" id="lunarDisplay"></div>
      <div id="weekdayDisplay"></div>
    </div>
  </div>

  <div class="content-row" id="contentRow">
    <div class="poster-area" id="posterArea">
      <div class="no-poster" id="noPoster">暂无海报</div>
    </div>
    <div class="info-area">
      <div class="movie-title" id="movieTitle"></div>
      <div class="movie-meta" id="movieMeta"></div>
      <div class="quote-area" id="quoteArea">“”</div>
    </div>
  </div>
</div>

<div class="nav-bar">
  <button class="nav-btn" id="prevBtn">&lt;</button>
  <div class="nav-date">
    <span id="navDateLabel"></span><br>
    <input class="goto-input" id="gotoInput" type="text" placeholder="MMDD" maxlength="4">
    <button class="nav-btn" id="gotoBtn" style="font-size:12px;padding:2px 8px;min-width:auto;">跳转</button>
  </div>
  <button class="nav-btn" id="nextBtn">&gt;</button>
</div>

<script>
// ========== 全年数据 ==========
var ENTRIES = ''' + data_json + ''';

// 按 MMDD 索引
var MAP = {};
for (var i = 0; i < ENTRIES.length; i++) {
  var e = ENTRIES[i];
  var key = pad(e.m, 2) + pad(e.d, 2);
  MAP[key] = e;
}

function pad(n, w) {
  var s = String(n);
  while (s.length < w) s = '0' + s;
  return s;
}

// 农历数据
var LUNAR_MONTH = ['', '正月', '二月', '三月', '四月', '五月', '六月',
                   '七月', '八月', '九月', '十月', '冬月', '腊月'];
var LUNAR_DAY = ['', '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
                 '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
                 '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十'];
var WEEKDAY = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

// ========== 当前状态 ==========
var curYear = 2026;
// 默认显示当天
var today = new Date();
var curMonth = today.getMonth() + 1;
var curDay = today.getDate();

// 但如果当前不是2026年，默认显示1月1日
if (today.getFullYear() !== 2026) {
  curMonth = 1;
  curDay = 1;
}

// ========== 渲染 ==========
function render(m, d) {
  var key = pad(m, 2) + pad(d, 2);
  var entry = MAP[key];
  if (!entry) {
    document.getElementById('dayBig').textContent = pad(d, 2);
    document.getElementById('dateSuffix').textContent = '/ ' + pad(m, 2);
    document.getElementById('lunarDisplay').textContent = '';
    document.getElementById('weekdayDisplay').textContent = '';
    document.getElementById('movieTitle').innerHTML = '无数据';
    document.getElementById('movieMeta').textContent = '';
    document.getElementById('quoteArea').innerHTML = '';
    document.getElementById('noPoster').style.display = 'flex';
    var img = document.getElementById('posterArea').querySelector('img');
    if (img) img.remove();
    return;
  }

  // 日期
  var dt = new Date(curYear, m - 1, d);
  var wd = WEEKDAY[dt.getDay()];
  document.getElementById('dayBig').textContent = pad(d, 2);
  document.getElementById('dateSuffix').textContent = '/ ' + pad(m, 2);
  document.getElementById('weekdayDisplay').textContent = wd;

  // 农历
  document.getElementById('lunarDisplay').textContent = entry.lunar || '';

  // 电影名
  var titleHtml = entry.t;
  if (entry.url) {
    titleHtml = '<a href="' + entry.url + '">' + entry.t + '</a>';
  }
  if (entry.r) {
    var starStr = '';
    if (entry.s) {
      var full = Math.floor(entry.s);
      for (var si = 0; si < full; si++) starStr += '★';
      if (entry.s - full >= 0.5) starStr += '☆';
    }
    var ratingStr = entry.r + ' ' + starStr;
    titleHtml += ' <span style="font-size:14px;font-weight:400;color:#888;">' + ratingStr + '</span>';
  }
  document.getElementById('movieTitle').innerHTML = titleHtml;

  // 元信息
  var metaParts = [];
  if (entry.dir) metaParts.push('导演: ' + entry.dir);
  if (entry.year) metaParts.push(entry.year);
  if (entry.gen) metaParts.push(entry.gen);
  document.getElementById('movieMeta').textContent = metaParts.join(' · ') || '';

  // 台词
  document.getElementById('quoteArea').innerHTML = '“' + (entry.q || '') + '”';

  // 海报
  var existingImg = document.getElementById('posterArea').querySelector('img');
  var noPoster = document.getElementById('noPoster');
  if (entry.poster) {
    if (noPoster) noPoster.style.display = 'none';
    if (!existingImg) {
      var img = document.createElement('img');
      img.id = 'moviePosterImg';
      document.getElementById('posterArea').appendChild(img);
      existingImg = img;
    }
    existingImg.src = entry.poster;
    existingImg.style.display = 'block';
  } else {
    if (noPoster) noPoster.style.display = 'flex';
    if (existingImg) existingImg.style.display = 'none';
  }

  // 导航标签
  document.getElementById('navDateLabel').textContent = m + '月' + d + '日';
  document.getElementById('gotoInput').value = key;

  // 更新按钮状态
  var prevBtn = document.getElementById('prevBtn');
  var nextBtn = document.getElementById('nextBtn');
  // 检查是否有前一天/后一天的数据
  var prevKey = getPrevKey(m, d);
  var nextKey = getNextKey(m, d);
  prevBtn.className = 'nav-btn' + (prevKey ? '' : ' disabled');
  nextBtn.className = 'nav-btn' + (nextKey ? '' : ' disabled');
}

function getPrevKey(m, d) {
  var keys = Object.keys(MAP).sort();
  var cur = pad(m, 2) + pad(d, 2);
  var idx = keys.indexOf(cur);
  if (idx > 0) return keys[idx - 1];
  return null;
}

function getNextKey(m, d) {
  var keys = Object.keys(MAP).sort();
  var cur = pad(m, 2) + pad(d, 2);
  var idx = keys.indexOf(cur);
  if (idx >= 0 && idx < keys.length - 1) return keys[idx + 1];
  return null;
}

// ========== 时钟 ==========
function updateClock() {
  var now = new Date();
  var h = pad(now.getHours(), 2);
  var min = pad(now.getMinutes(), 2);
  document.getElementById('clockDisplay').textContent = h + ':' + min;
  // 模拟电池
  document.getElementById('batteryDisplay').textContent = '🔋' + Math.floor(Math.random() * 20 + 60) + '%';
}
updateClock();
setInterval(updateClock, 30000);

// ========== 导航事件 ==========
document.getElementById('prevBtn').addEventListener('click', function() {
  var key = getPrevKey(curMonth, curDay);
  if (key) {
    curMonth = parseInt(key.substring(0, 2), 10);
    curDay = parseInt(key.substring(2, 4), 10);
    render(curMonth, curDay);
  }
});

document.getElementById('nextBtn').addEventListener('click', function() {
  var key = getNextKey(curMonth, curDay);
  if (key) {
    curMonth = parseInt(key.substring(0, 2), 10);
    curDay = parseInt(key.substring(2, 4), 10);
    render(curMonth, curDay);
  }
});

document.getElementById('gotoBtn').addEventListener('click', function() {
  var val = document.getElementById('gotoInput').value.trim();
  if (val.length === 4) {
    var mm = parseInt(val.substring(0, 2), 10);
    var dd = parseInt(val.substring(2, 4), 10);
    if (MAP[val]) {
      curMonth = mm;
      curDay = dd;
      render(curMonth, curDay);
    }
  }
});

document.getElementById('gotoInput').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    document.getElementById('gotoBtn').click();
  }
});

// ========== 初始渲染 ==========
// 把农历数据附加到条目
// 注意：这里需要从后端传过来的农历数据
// 如果后端没传，就用 JS 简单显示
render(curMonth, curDay);
</script>

</body>
</html>'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


def main():
    print("=" * 50)
    print("豆瓣电影日历 - Kindle桌面日历面板版")
    print("=" * 50)

    out_dir = os.path.dirname(os.path.abspath(__file__))

    # Step 1: Scrape
    print("\n[1/3] 爬取数据...")
    items = scrape_all()
    print(f"  共 {len(items)} 条")

    # Step 2: 附加农历信息
    print("\n[2/3] 计算农历日期...")
    for item in items:
        m, d = item['month'], item['day']
        item['lunar'] = get_lunar_str(2026, m, d)

    # Step 3: 生成日历面板 HTML
    print("[3/3] 生成日历面板HTML...")
    output = os.path.join(out_dir, 'kindle_calendar_panel.html')
    generate_calendar_html(items, output, embed_images=True)
    
    size_kb = round(os.path.getsize(output) / 1024, 1)
    print(f"\n✅ 完成！")
    print(f"📁 {output} ({size_kb}KB)")
    print(f"\n🌐 在线版已部署在 GitHub Pages:")
    print(f"   https://kongyuan.github.io/douban-calendar-2026/")


if __name__ == '__main__':
    main()
