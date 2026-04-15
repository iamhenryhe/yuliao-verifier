#!/bin/zsh
set -euo pipefail

项目目录="$(cd "$(dirname "$0")" && pwd)"
下载目录="/Users/zijiehe/Downloads"
今天="$(date +%F)"

源板块="$下载目录/t-$今天.csv"
源个股="$下载目录/t-$今天 (1).csv"
目标板块="$项目目录/data/板块.csv"
目标个股="$项目目录/data/个股.csv"

if [[ ! -f "$源板块" ]]; then
  echo "缺少文件: $源板块"
  exit 1
fi

if [[ ! -f "$源个股" ]]; then
  echo "缺少文件: $源个股"
  exit 1
fi

cp "$源板块" "$目标板块"
cp "$源个股" "$目标个股"

cd "$项目目录"
python build_site.py

git add data/板块.csv data/个股.csv site/index.html
git commit -m "更新 $今天 数据" || echo "没有变化，无需提交"
git push
