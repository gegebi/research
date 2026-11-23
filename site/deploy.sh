#!/bin/zsh
# 새 리포트를 반영해서 다시 배포한다: ./deploy.sh
cd "$(dirname "$0")" && python3 make_site.py && npx --yes vercel@66.6.0 deploy --prod --yes
