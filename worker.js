// ============================================
// KINO DRAMA — Cloudflare Worker Stream Proxy
// ============================================

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS headers
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': '*',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: cors });
    }

    // Health check
    if (url.pathname === '/' || url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'ok', service: 'KINO DRAMA Stream' }), {
        headers: { ...cors, 'Content-Type': 'application/json' }
      });
    }

    // /stream?file_id=XXX&token=YYY
    if (url.pathname === '/stream') {
      const file_id = url.searchParams.get('file_id');
      const token   = url.searchParams.get('token');

      if (!file_id || !token) {
        return new Response('file_id va token kerak', { status: 400, headers: cors });
      }

      try {
        // 1. file_path olish
        const getFileResp = await fetch(
          `https://api.telegram.org/bot${token}/getFile?file_id=${encodeURIComponent(file_id)}`
        );
        const getFileData = await getFileResp.json();

        if (!getFileData.ok) {
          // file_path yo'q (20MB+ fayl) — MTProto kerak, lekin biz
          // Telegram CDN dan to'g'ridan oqim qilamiz
          return new Response(
            JSON.stringify({ error: 'Fayl juda katta (20MB+), Telegram file_path bermadi', code: getFileData.error_code }),
            { status: 502, headers: { ...cors, 'Content-Type': 'application/json' } }
          );
        }

        const filePath = getFileData.result.file_path;
        const telegramUrl = `https://api.telegram.org/file/bot${token}/${filePath}`;

        // Range header ni o'tkazib yuborish (video seeking uchun muhim)
        const rangeHeader = request.headers.get('Range');
        const fetchHeaders = {};
        if (rangeHeader) fetchHeaders['Range'] = rangeHeader;

        // 2. Telegram CDN dan stream
        const videoResp = await fetch(telegramUrl, { headers: fetchHeaders });

        const respHeaders = {
          ...cors,
          'Content-Type': videoResp.headers.get('Content-Type') || 'video/mp4',
          'Accept-Ranges': 'bytes',
          'Cache-Control': 'public, max-age=3600',
        };

        if (videoResp.headers.get('Content-Length')) {
          respHeaders['Content-Length'] = videoResp.headers.get('Content-Length');
        }
        if (videoResp.headers.get('Content-Range')) {
          respHeaders['Content-Range'] = videoResp.headers.get('Content-Range');
        }

        return new Response(videoResp.body, {
          status: videoResp.status,
          headers: respHeaders,
        });

      } catch (e) {
        return new Response('Server xatosi: ' + e.message, { status: 500, headers: cors });
      }
    }

    return new Response('Topilmadi', { status: 404, headers: cors });
  }
};
