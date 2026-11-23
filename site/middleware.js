// 모든 요청을 HTTP Basic 인증으로 막는다. 비밀번호는 코드에 없고 Vercel 환경변수 SITE_PASSWORD에만 있다.
import { next } from '@vercel/functions';

export const config = { matcher: '/:path*' };

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export default function middleware(request) {
  const expected = process.env.SITE_PASSWORD;
  const deny = () =>
    new Response('비밀번호가 필요합니다.', {
      status: 401,
      headers: {
        'WWW-Authenticate': 'Basic realm="Daily Science", charset="UTF-8"',
        'Cache-Control': 'no-store',
      },
    });
  if (!expected) return deny(); // 환경변수가 없으면 열어두지 않고 막는다

  const header = request.headers.get('authorization') || '';
  if (!header.startsWith('Basic ')) return deny();
  let pass = '';
  try {
    const bytes = Uint8Array.from(atob(header.slice(6)), (c) => c.charCodeAt(0));
    const decoded = new TextDecoder().decode(bytes);
    pass = decoded.slice(decoded.indexOf(':') + 1); // 아이디 칸은 아무거나 가능
  } catch {
    return deny();
  }
  return safeEqual(pass, expected) ? next() : deny();
}
