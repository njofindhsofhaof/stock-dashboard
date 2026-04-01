#!/bin/bash
# Chạy 1 lần duy nhất để tạo GitHub repo và push tất cả file
# Yêu cầu: gh CLI đã đăng nhập (gh auth login)

set -e
REPO="stock-dashboard"
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "══════════════════════════════════════════"
echo "  📊 Stock Dashboard – GitHub Setup"
echo "══════════════════════════════════════════"

# Kiểm tra gh CLI
if ! command -v gh &>/dev/null; then
  echo "❌ Chưa cài gh CLI. Chạy: brew install gh"
  exit 1
fi

# Kiểm tra đã đăng nhập chưa
if ! gh auth status &>/dev/null; then
  echo "❌ Chưa đăng nhập GitHub. Chạy: gh auth login"
  exit 1
fi

OWNER=$(gh api user --jq .login)
echo "  ✅ Đăng nhập: $OWNER"
echo ""

# Init git nếu chưa có
if [ ! -d .git ]; then
  git init
  git branch -M main
fi

# Tạo .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
.DS_Store
*.command
stock_server.py
EOF

# Commit tất cả
git add stock_dashboard.html fetch_data.py stock_data.json .github/
git add .gitignore 2>/dev/null || true
git diff --staged --quiet || git commit -m "🚀 Initial commit: Stock Dashboard"

# Tạo repo public và push
echo "  Đang tạo repo '$REPO'..."
if gh repo view "$OWNER/$REPO" &>/dev/null; then
  echo "  Repo đã tồn tại, push lên..."
  git remote set-url origin "https://github.com/$OWNER/$REPO.git" 2>/dev/null || \
  git remote add origin "https://github.com/$OWNER/$REPO.git"
  git push -u origin main
else
  gh repo create "$REPO" --public --source=. --remote=origin --push
fi

# Bật GitHub Pages
echo ""
echo "  Đang bật GitHub Pages..."
gh api -X POST "repos/$OWNER/$REPO/pages" \
  -f build_type=legacy \
  -f source[branch]=main \
  -f source[path]=/ 2>/dev/null && echo "  ✅ Pages đã bật" || \
gh api -X PUT "repos/$OWNER/$REPO/pages" \
  -f source[branch]=main \
  -f source[path]=/ 2>/dev/null && echo "  ✅ Pages đã cập nhật" || \
echo "  ℹ  Hãy vào Settings → Pages → Deploy from branch → main → / để bật thủ công"

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ XONG!"
echo ""
echo "  📁 Repo:      https://github.com/$OWNER/$REPO"
echo "  🌐 Dashboard: https://$OWNER.github.io/$REPO/stock_dashboard.html"
echo ""
echo "  ⏰ Data sẽ tự cập nhật mỗi 15 phút trong giờ giao dịch"
echo "  🔧 Để chạy thủ công: vào GitHub → Actions → Run workflow"
echo "══════════════════════════════════════════"
echo ""
