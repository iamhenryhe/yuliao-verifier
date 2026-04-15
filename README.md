# 语料验证器

这是一个可直接放到 GitHub 的静态网站项目。

网站用途：

- 看板块排行
- 看个股排行
- 点板块或个股后，查看对应支撑语料

## 目录说明

```text
语料验证器/
  .github/
    workflows/
      deploy.yml
  data/
    板块.csv
    个股.csv
  site/
    index.html
    .nojekyll
  build_site.py
  requirements.txt
  更新数据.sh
  README.md
```

## 首次发布步骤

### 1. 新建 GitHub 仓库

仓库名可以直接叫：

```text
语料验证器
```

### 2. 上传整个文件夹

把当前整个文件夹上传到 GitHub 仓库根目录。

### 3. 打开 GitHub Pages

进入仓库：

- `Settings`
- `Pages`
- `Build and deployment`
- 选择 `GitHub Actions`

之后每次你推送更新，GitHub 都会自动重新发布网站。

## 每天更新数据的方法

你每天只需要替换这两个文件：

- `data/板块.csv`
- `data/个股.csv`

对应关系：

- 当天的 `t-YYYY-MM-DD.csv` -> `data/板块.csv`
- 当天的 `t-YYYY-MM-DD (1).csv` -> `data/个股.csv`

替换后执行：

```bash
python build_site.py
git add .
git commit -m "更新 2026-04-15 数据"
git push
```

推送完成后，GitHub Pages 会自动更新网站。

## 更省事的方法

项目里已经带了一个脚本：

```bash
./更新数据.sh
```

这个脚本会自动：

1. 去 `~/Downloads` 找今天的两个 `t` 文件
2. 覆盖到 `data/板块.csv` 和 `data/个股.csv`
3. 重新生成 `site/index.html`
4. 自动执行 `git add / commit / push`

### 先给脚本执行权限

```bash
chmod +x 更新数据.sh
```

### 然后每天执行

```bash
./更新数据.sh
```

## 本地预览

在项目目录里执行：

```bash
python -m http.server 8765
```

然后打开：

```text
http://127.0.0.1:8765/site/
```

## 注意

### 1. 网站本身是静态的

网站不会自己读取你电脑里的下载目录。

所以“自动更新”的前提是：

- 你手动替换 `data` 里的两个文件，或者
- 你在自己电脑上运行 `更新数据.sh`

### 2. 如果用了 `更新数据.sh`

需要满足：

- 电脑开着
- 今天的两个文件已经在 `~/Downloads`
- 文件名格式保持不变

### 3. 页面入口

GitHub Pages 发布后，最终访问地址一般是：

```text
https://你的用户名.github.io/仓库名/
```
