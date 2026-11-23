// 새로고침 버튼용: GitHub Actions 워크플로를 실행시킨다. middleware.js 의 비밀번호 검사를 먼저 통과해야 도달한다.
export function POST(request) {
  const origin = request.headers.get('origin');
  const host = request.headers.get('host');
  if (!origin || new URL(origin).host !== host) {
    return Response.json({ error: 'forbidden' }, { status: 403 });
  }
  const repo = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!repo || !token) return Response.json({ error: 'not configured' }, { status: 500 });

  return fetch(`https://api.github.com/repos/${repo}/actions/workflows/daily.yml/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'daily-science-site',
    },
    body: JSON.stringify({ ref: 'main' }),
  }).then((r) =>
    r.status === 204
      ? Response.json({ ok: true })
      : Response.json({ error: 'github ' + r.status }, { status: 502 })
  );
}
