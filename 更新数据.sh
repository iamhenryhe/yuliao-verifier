#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOWNLOAD_DIR="/Users/zijiehe/Downloads"
TODAY="$(date +%F)"

SRC_SECTOR="$DOWNLOAD_DIR/t-$TODAY.csv"
SRC_COMPANY="$DOWNLOAD_DIR/t-$TODAY (1).csv"
DST_SECTOR="$PROJECT_DIR/data/板块.csv"
DST_COMPANY="$PROJECT_DIR/data/个股.csv"

if [[ ! -f "$SRC_SECTOR" ]]; then
  echo "缺少文件: $SRC_SECTOR"
  exit 1
fi

if [[ ! -f "$SRC_COMPANY" ]]; then
  echo "缺少文件: $SRC_COMPANY"
  exit 1
fi

cp "$SRC_SECTOR" "$DST_SECTOR"
cp "$SRC_COMPANY" "$DST_COMPANY"

cd "$PROJECT_DIR"
python build_site.py

git add data/板块.csv data/个股.csv site/index.html
git commit -m "更新 $TODAY 数据" || echo "没有变化，无需提交"
git push
