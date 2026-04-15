from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SITE_DIR = BASE_DIR / "site"
SECTOR_CSV = DATA_DIR / "板块.csv"
COMPANY_CSV = DATA_DIR / "个股.csv"
OUTPUT_HTML = SITE_DIR / "index.html"


TAG_RE = re.compile(r"<e\b[^>]*\/>")
WS_RE = re.compile(r"[ \t\r\f\v]+")
BLANKS_RE = re.compile(r"\n{3,}")


def clean_content(text: str) -> str:
    text = str(text or "")
    text = text.replace("_x000D_", "\n")
    text = TAG_RE.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    text = BLANKS_RE.sub("\n\n", text).strip()
    return text


def content_key(text: str) -> str:
    normalized = clean_content(text)
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


@dataclass
class Evidence:
    key: str
    content: str
    sectors: set[str] = field(default_factory=set)
    companies: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    sector_rows: int = 0
    company_rows: int = 0
    timestamps: list[str] = field(default_factory=list)

    def to_dict(self, idx: int) -> dict:
        sectors = sorted(self.sectors)
        companies = sorted(self.companies)
        preview = self.content[:220] + ("..." if len(self.content) > 220 else "")
        return {
            "id": f"evidence-{idx}",
            "content": self.content,
            "preview": preview,
            "sectors": sectors,
            "companies": companies,
            "sources": sorted(self.sources),
            "sectorRowCount": self.sector_rows,
            "companyRowCount": self.company_rows,
            "timestampCount": len(self.timestamps),
            "timestamps": sorted(set(self.timestamps)),
        }


def build_payload() -> dict:
    sector_df = pd.read_csv(SECTOR_CSV).fillna("")
    company_df = pd.read_csv(COMPANY_CSV).fillna("")

    evidence_map: dict[str, Evidence] = {}
    sector_row_counts: defaultdict[str, int] = defaultdict(int)
    company_row_counts: defaultdict[str, int] = defaultdict(int)

    for _, row in sector_df.iterrows():
        raw_content = row.get("content", "")
        key = content_key(raw_content)
        if not key:
            continue
        evidence = evidence_map.setdefault(
            key,
            Evidence(key=key, content=clean_content(raw_content)),
        )
        sector = str(row.get("sector", "")).strip()
        source = str(row.get("source", "")).strip()
        timestamp = str(row.get("timestamp", "")).strip()
        if sector:
            evidence.sectors.add(sector)
            evidence.sector_rows += 1
            sector_row_counts[sector] += 1
        if source:
            evidence.sources.add(source)
        if timestamp:
            evidence.timestamps.append(timestamp)

    for _, row in company_df.iterrows():
        raw_content = row.get("content", "")
        key = content_key(raw_content)
        if not key:
            continue
        evidence = evidence_map.setdefault(
            key,
            Evidence(key=key, content=clean_content(raw_content)),
        )
        company = str(row.get("company", "")).strip()
        source = str(row.get("source", "")).strip()
        timestamp = str(row.get("timestamp", "")).strip()
        if company:
            evidence.companies.add(company)
            evidence.company_rows += 1
            company_row_counts[company] += 1
        if source:
            evidence.sources.add(source)
        if timestamp:
            evidence.timestamps.append(timestamp)

    evidences = sorted(
        (ev.to_dict(idx) for idx, ev in enumerate(evidence_map.values(), start=1)),
        key=lambda item: (
            -item["sectorRowCount"],
            -item["companyRowCount"],
            item["preview"],
        ),
    )

    sector_evidence_counts: defaultdict[str, int] = defaultdict(int)
    sector_company_links: defaultdict[str, set[str]] = defaultdict(set)
    company_evidence_counts: defaultdict[str, int] = defaultdict(int)
    company_sector_links: defaultdict[str, set[str]] = defaultdict(set)

    for ev in evidences:
        for sector in ev["sectors"]:
            sector_evidence_counts[sector] += 1
            sector_company_links[sector].update(ev["companies"])
        for company in ev["companies"]:
            company_evidence_counts[company] += 1
            company_sector_links[company].update(ev["sectors"])

    sectors = sorted(
        (
            {
                "name": sector,
                "outputCount": sector_row_counts[sector],
                "evidenceCount": sector_evidence_counts[sector],
                "companyCount": len(sector_company_links[sector]),
                "companies": sorted(sector_company_links[sector]),
            }
            for sector in sector_row_counts
        ),
        key=lambda item: (-item["outputCount"], -item["evidenceCount"], item["name"]),
    )

    companies = sorted(
        (
            {
                "name": company,
                "outputCount": company_row_counts[company],
                "evidenceCount": company_evidence_counts[company],
                "sectorCount": len(company_sector_links[company]),
                "sectors": sorted(company_sector_links[company]),
            }
            for company in company_row_counts
        ),
        key=lambda item: (-item["outputCount"], -item["evidenceCount"], item["name"]),
    )

    sector_rank = {item["name"]: idx + 1 for idx, item in enumerate(sectors)}

    payload = {
        "generatedAt": pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "uniqueEvidenceCount": len(evidences),
            "sectorRowCount": int(len(sector_df)),
            "companyRowCount": int(len(company_df)),
            "sectorCount": len(sectors),
            "companyCount": len(companies),
            "robotRank": sector_rank.get("机器人"),
            "robotOutputCount": sector_row_counts.get("机器人", 0),
            "robotEvidenceCount": sector_evidence_counts.get("机器人", 0),
        },
        "sources": {
            "sectorCsv": str(SECTOR_CSV),
            "companyCsv": str(COMPANY_CSV),
        },
        "sectors": sectors,
        "companies": companies,
        "evidences": evidences,
    }
    return payload


def render_html(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>语料查证器</title>
  <style>
    :root {{
      --背景: #f5f5f7;
      --面板: #ffffff;
      --面板浅: #fbfbfd;
      --边框: #d2d2d7;
      --边框强: #c7c7cc;
      --文字: #1d1d1f;
      --次要: rgba(29,29,31,0.72);
      --强调: #0071e3;
      --强调浅: #e8f3ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--背景);
      color: var(--文字);
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    }}
    .页面 {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
    }}
    .侧栏 {{
      position: sticky;
      top: 0;
      height: 100vh;
      overflow: auto;
      padding: 18px;
      border-right: 1px solid var(--边框);
      background: rgba(255,255,255,0.88);
      backdrop-filter: saturate(180%) blur(20px);
    }}
    .标题块, .侧块, .主块 {{
      border: 1px solid var(--边框);
      border-radius: 8px;
      background: var(--面板);
    }}
    .标题块 {{
      padding: 18px;
      font-size: 34px;
      font-weight: 700;
      line-height: 1.1;
    }}
    .侧块 {{
      margin-top: 16px;
      padding: 14px;
    }}
    .侧块标题 {{
      margin: 0 0 12px;
      font-size: 18px;
      font-weight: 650;
    }}
    .排行列表 {{
      display: grid;
      gap: 8px;
    }}
    .排行按钮 {{
      width: 100%;
      padding: 12px;
      border-radius: 8px;
      border: 1px solid var(--边框);
      background: var(--面板浅);
      color: var(--文字);
      text-align: left;
      cursor: pointer;
    }}
    .排行按钮.选中 {{
      border-color: var(--强调);
      background: var(--强调浅);
    }}
    .排行主行 {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: 15px;
      font-weight: 620;
    }}
    .排行副行 {{
      margin-top: 6px;
      font-size: 12px;
      color: var(--次要);
    }}
    .主体 {{
      min-width: 0;
      padding: 22px;
    }}
    .工具条 {{
      position: sticky;
      top: 0;
      z-index: 5;
      padding-bottom: 14px;
      background: linear-gradient(180deg, rgba(245,245,247,.96) 0%, rgba(245,245,247,.9) 75%, rgba(245,245,247,0) 100%);
    }}
    .工具格 {{
      display: grid;
      grid-template-columns: minmax(260px, .7fr) minmax(320px, 1fr) auto;
      gap: 12px;
      align-items: end;
    }}
    .字段 {{
      display: grid;
      gap: 6px;
    }}
    .字段标签 {{
      font-size: 13px;
      color: var(--次要);
    }}
    .输入框, .下拉框, .按钮 {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 8px;
      border: 1px solid var(--边框);
      background: var(--面板);
      color: var(--文字);
      font-size: 14px;
      outline: none;
    }}
    .输入框:focus, .下拉框:focus {{
      border-color: var(--强调);
      box-shadow: 0 0 0 3px rgba(0,113,227,.16);
    }}
    .按钮 {{
      cursor: pointer;
      font-weight: 620;
    }}
    .按钮.主按钮 {{
      background: var(--强调);
      border-color: var(--强调);
      color: #ffffff;
    }}
    .统计栏 {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .统计卡 {{
      padding: 14px;
      border: 1px solid var(--边框);
      border-radius: 8px;
      background: var(--面板);
    }}
    .统计名 {{
      font-size: 12px;
      color: var(--次要);
      margin-bottom: 8px;
    }}
    .统计值 {{
      font-size: 28px;
      font-weight: 700;
    }}
    .主块 {{
      padding: 18px;
    }}
    .主块标题行 {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 14px;
    }}
    .主块标题 {{
      margin: 0;
      font-size: 28px;
      font-weight: 700;
    }}
    .结果数 {{
      color: var(--次要);
      font-size: 15px;
    }}
    .语料列表 {{
      display: grid;
      gap: 14px;
    }}
    .语料卡 {{
      padding: 18px;
      border-radius: 8px;
      border: 1px solid var(--边框);
      background: var(--面板浅);
    }}
    .语料头 {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      align-items: center;
    }}
    .语料编号 {{
      font-size: 16px;
      font-weight: 650;
    }}
    .语料统计 {{
      color: var(--次要);
      font-size: 13px;
    }}
    .信息行 {{
      margin: 8px 0 0;
      line-height: 1.7;
      font-size: 14px;
      color: var(--文字);
    }}
    .信息标题 {{
      color: var(--次要);
    }}
    .正文 {{
      margin-top: 12px;
      white-space: pre-wrap;
      line-height: 1.78;
      font-size: 15px;
      color: var(--文字);
      max-height: 9.2em;
      overflow: hidden;
      position: relative;
    }}
    .语料卡.展开 .正文 {{
      max-height: none;
    }}
    .正文::after {{
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 36px;
      background: linear-gradient(180deg, rgba(251,251,253,0), rgba(251,251,253,1));
    }}
    .语料卡.展开 .正文::after {{
      display: none;
    }}
    .操作行 {{
      margin-top: 14px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .小按钮 {{
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid var(--边框);
      background: var(--面板);
      color: var(--文字);
      font-size: 13px;
      cursor: pointer;
    }}
    .空状态 {{
      padding: 28px;
      text-align: center;
      border-radius: 8px;
      border: 1px dashed var(--边框强);
      color: var(--次要);
    }}
    @media (max-width: 1200px) {{
      .页面 {{
        grid-template-columns: 1fr;
      }}
      .侧栏 {{
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--边框);
      }}
      .工具格 {{
        grid-template-columns: 1fr;
      }}
      .统计栏 {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 720px) {{
      .统计栏 {{
        grid-template-columns: 1fr;
      }}
      .主体, .侧栏 {{
        padding: 16px;
      }}
    }}
  </style>
</head>
<body>
  <div class="页面">
    <aside class="侧栏">
      <div class="标题块">语料查证器</div>
      <div class="侧块">
        <h2 class="侧块标题">板块排行</h2>
        <div class="排行列表" id="板块排行"></div>
      </div>
      <div class="侧块">
        <h2 class="侧块标题">个股排行</h2>
        <div class="排行列表" id="个股排行"></div>
      </div>
    </aside>

    <main class="主体">
      <div class="工具条">
        <div class="工具格">
          <div class="字段">
            <label class="字段标签" for="板块筛选">板块跳转</label>
            <select class="下拉框" id="板块筛选"></select>
          </div>
          <div class="字段">
            <label class="字段标签" for="个股搜索">个股跳转</label>
            <input class="输入框" id="个股搜索" list="个股列表" placeholder="输入个股后跳转" />
            <datalist id="个股列表"></datalist>
          </div>
          <button class="按钮 主按钮" id="跳转个股">跳到个股</button>
        </div>
      </div>

      <section class="统计栏">
        <div class="统计卡">
          <div class="统计名">去重语料</div>
          <div class="统计值" id="去重语料数"></div>
        </div>
        <div class="统计卡">
          <div class="统计名">板块输出总数</div>
          <div class="统计值" id="板块输出数"></div>
        </div>
        <div class="统计卡">
          <div class="统计名">个股输出总数</div>
          <div class="统计值" id="个股输出数"></div>
        </div>
      </section>

      <section class="主块">
        <div class="主块标题行">
          <h2 class="主块标题">支撑语料</h2>
          <div class="结果数" id="结果数"></div>
        </div>
        <div class="语料列表" id="语料列表"></div>
      </section>
    </main>
  </div>

  <script>
    const 数据 = {data_json};
    const 状态 = {{ 板块: '', 个股: '' }};
    const 数字 = new Intl.NumberFormat('zh-CN');

    const 元素 = {{
      板块筛选: document.getElementById('板块筛选'),
      个股搜索: document.getElementById('个股搜索'),
      个股列表: document.getElementById('个股列表'),
      跳转个股: document.getElementById('跳转个股'),
      去重语料数: document.getElementById('去重语料数'),
      板块输出数: document.getElementById('板块输出数'),
      个股输出数: document.getElementById('个股输出数'),
      板块排行: document.getElementById('板块排行'),
      个股排行: document.getElementById('个股排行'),
      结果数: document.getElementById('结果数'),
      语料列表: document.getElementById('语料列表'),
    }};

    function 转义(文本) {{
      return String(文本 ?? '').replace(/[&<>"]/g, 字 => ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }})[字]);
    }}

    function 写入统计() {{
      const 汇总 = 数据.summary;
      元素.去重语料数.textContent = 数字.format(汇总.uniqueEvidenceCount);
      元素.板块输出数.textContent = 数字.format(汇总.sectorRowCount);
      元素.个股输出数.textContent = 数字.format(汇总.companyRowCount);
    }}

    function 写入筛选器() {{
      元素.板块筛选.innerHTML = ['<option value="">全部板块</option>']
        .concat(数据.sectors.map(项 => `<option value="${{转义(项.name)}}">${{转义(项.name)}}</option>`))
        .join('');
      元素.个股列表.innerHTML = 数据.companies
        .map(项 => `<option value="${{转义(项.name)}}"></option>`)
        .join('');
    }}

    function 写入排行() {{
      元素.板块排行.innerHTML = 数据.sectors.slice(0, 14).map(项 => `
        <button class="排行按钮 ${{状态.板块 === 项.name ? '选中' : ''}}" data-板块="${{转义(项.name)}}">
          <div class="排行主行"><span>${{转义(项.name)}}</span><span>${{数字.format(项.outputCount)}} 条</span></div>
          <div class="排行副行">支撑语料 ${{数字.format(项.evidenceCount)}} 条</div>
        </button>
      `).join('');
      元素.个股排行.innerHTML = 数据.companies.slice(0, 14).map(项 => `
        <button class="排行按钮 ${{状态.个股 === 项.name ? '选中' : ''}}" data-个股="${{转义(项.name)}}">
          <div class="排行主行"><span>${{转义(项.name)}}</span><span>${{数字.format(项.outputCount)}} 条</span></div>
          <div class="排行副行">支撑语料 ${{数字.format(项.evidenceCount)}} 条</div>
        </button>
      `).join('');
    }}

    function 取结果() {{
      return 数据.evidences.filter(语料 => {{
        if (状态.板块 && !语料.sectors.includes(状态.板块)) return false;
        if (状态.个股 && !语料.companies.includes(状态.个股)) return false;
        return true;
      }});
    }}

    function 写入结果() {{
      const 结果 = 取结果();
      元素.结果数.textContent = `当前结果 ${{数字.format(结果.length)}} 条`;
      if (!结果.length) {{
        元素.语料列表.innerHTML = '<div class="空状态">没有找到支撑语料。</div>';
        return;
      }}
      元素.语料列表.innerHTML = 结果.map((语料, 序号) => `
        <article class="语料卡" id="${{语料.id}}">
          <div class="语料头">
            <div class="语料编号">语料 ${{序号 + 1}}</div>
            <div class="语料统计">板块行数 ${{数字.format(语料.sectorRowCount)}}　个股行数 ${{数字.format(语料.companyRowCount)}}</div>
          </div>
          <div class="信息行"><span class="信息标题">板块：</span>${{转义(语料.sectors.join('、') || '无')}}</div>
          <div class="信息行"><span class="信息标题">个股：</span>${{转义(语料.companies.join('、') || '无')}}</div>
          <div class="正文">${{转义(语料.content)}}</div>
          <div class="操作行">
            <button class="小按钮" data-展开="${{语料.id}}">展开 / 收起</button>
            <button class="小按钮" data-复制="${{语料.id}}">复制语料</button>
          </div>
        </article>
      `).join('');
    }}

    function 同步控件() {{
      元素.板块筛选.value = 状态.板块;
      元素.个股搜索.value = 状态.个股;
    }}

    function 写入地址() {{
      const 参数 = new URLSearchParams();
      if (状态.板块) 参数.set('板块', 状态.板块);
      if (状态.个股) 参数.set('个股', 状态.个股);
      history.replaceState(null, '', `${{location.pathname}}#${{参数.toString()}}`);
    }}

    function 读取地址() {{
      const 片段 = location.hash.startsWith('#') ? location.hash.slice(1) : '';
      const 参数 = new URLSearchParams(片段);
      状态.板块 = 参数.get('板块') || '';
      状态.个股 = 参数.get('个股') || '';
    }}

    function 重绘() {{
      同步控件();
      写入排行();
      写入结果();
      写入地址();
    }}

    function 设板块(名称) {{
      状态.板块 = 名称 || '';
      if (状态.个股) {{
        const 个股 = 数据.companies.find(项 => 项.name === 状态.个股);
        if (个股 && 状态.板块 && !个股.sectors.includes(状态.板块)) {{
          状态.个股 = '';
        }}
      }}
      重绘();
      document.querySelector('.主块')?.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    function 设个股(名称) {{
      状态.个股 = 名称 || '';
      重绘();
      document.querySelector('.主块')?.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    document.addEventListener('click', async (事件) => {{
      const 板块按钮 = 事件.target.closest('[data-板块]');
      if (板块按钮) {{
        设板块(板块按钮.dataset.板块);
        return;
      }}
      const 个股按钮 = 事件.target.closest('[data-个股]');
      if (个股按钮) {{
        设个股(个股按钮.dataset.个股);
        return;
      }}
      const 展开按钮 = 事件.target.closest('[data-展开]');
      if (展开按钮) {{
        const 卡片 = document.getElementById(展开按钮.dataset.展开);
        if (卡片) {{
          卡片.classList.toggle('展开');
        }}
        return;
      }}
      const 复制按钮 = 事件.target.closest('[data-复制]');
      if (复制按钮) {{
        const 卡片 = document.getElementById(复制按钮.dataset.复制);
        const 文本 = 卡片?.querySelector('.正文')?.textContent || '';
        await navigator.clipboard.writeText(文本);
        复制按钮.textContent = '已复制';
        setTimeout(() => {{
          复制按钮.textContent = '复制语料';
        }}, 1200);
      }}
    }});

    元素.板块筛选.addEventListener('change', 事件 => {{
      状态.板块 = 事件.target.value;
      重绘();
    }});

    元素.跳转个股.addEventListener('click', () => {{
      const 词 = 元素.个股搜索.value.trim();
      if (!词) return;
      const 精确 = 数据.companies.find(项 => 项.name === 词);
      if (精确) {{
        设个股(精确.name);
        return;
      }}
      const 模糊 = 数据.companies.find(项 => 项.name.includes(词));
      if (模糊) {{
        元素.个股搜索.value = 模糊.name;
        设个股(模糊.name);
      }}
    }});

    元素.个股搜索.addEventListener('keydown', 事件 => {{
      if (事件.key === 'Enter') {{
        元素.跳转个股.click();
      }}
    }});

    读取地址();
    写入统计();
    写入筛选器();
    重绘();
  </script>
</body>
</html>
"""


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    OUTPUT_HTML.write_text(render_html(payload), encoding="utf-8")
    print(f"generated: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
