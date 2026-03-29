const express = require('express');
const https = require('https');
const http = require('http');
const app = express();

// CORS — barcha domendan ruxsat
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Range, Content-Type');
    res.header('Access-Control-Expose-Headers', 'Content-Range, Accept-Ranges, Content-Length');
    if(req.method === 'OPTIONS') return res.sendStatus(200);
    next();
});

// /stream?file_id=XXX&token=YYY
app.get('/stream', async (req, res) => {
    const { file_id, token } = req.query;

    if(!file_id || !token) {
        return res.status(400).json({ error: 'file_id va token kerak' });
    }

    try {
        // 1. getFile — file_path olish
        const fileMeta = await new Promise((resolve, reject) => {
            const url = `https://api.telegram.org/bot${token}/getFile?file_id=${encodeURIComponent(file_id)}`;
            https.get(url, (r) => {
                let data = '';
                r.on('data', chunk => data += chunk);
                r.on('end', () => {
                    try { resolve(JSON.parse(data)); }
                    catch(e) { reject(e); }
                });
            }).on('error', reject);
        });

        if(!fileMeta.ok) {
            // file_path yo'q (>20MB fayl) — to'g'ridan stream qilamiz
            // Telegram CDN dan stream
            return streamFromTelegramCDN(req, res, token, file_id);
        }

        const filePath = fileMeta.result.file_path;
        const fileUrl = `https://api.telegram.org/file/bot${token}/${filePath}`;

        // 2. Range header support (video seek uchun muhim)
        const rangeHeader = req.headers.range;
        streamFile(fileUrl, rangeHeader, res);

    } catch(err) {
        console.error('Stream xato:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// Faylni stream qilish (Range support bilan)
function streamFile(fileUrl, rangeHeader, res) {
    const urlObj = new URL(fileUrl);
    const options = {
        hostname: urlObj.hostname,
        path: urlObj.pathname + urlObj.search,
        method: 'GET',
        headers: {}
    };

    if(rangeHeader) {
        options.headers['Range'] = rangeHeader;
    }

    const proto = urlObj.protocol === 'https:' ? https : http;

    const tgReq = proto.request(options, (tgRes) => {
        const headers = {
            'Content-Type': tgRes.headers['content-type'] || 'video/mp4',
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'public, max-age=3600',
        };

        if(tgRes.headers['content-length']) {
            headers['Content-Length'] = tgRes.headers['content-length'];
        }
        if(tgRes.headers['content-range']) {
            headers['Content-Range'] = tgRes.headers['content-range'];
        }

        res.writeHead(tgRes.statusCode, headers);
        tgRes.pipe(res);
    });

    tgReq.on('error', (err) => {
        console.error('Pipe xato:', err.message);
        if(!res.headersSent) res.status(502).json({ error: 'Stream xatosi' });
    });

    tgReq.end();
}

// Katta fayllar uchun (>20MB) — Telegram CDN dan to'g'ridan stream
// Bu usul ishlashi uchun bot premium bo'lishi kerak yoki maxsus usul kerak
async function streamFromTelegramCDN(req, res, token, file_id) {
    // Katta fayllar uchun alternativ: sendVideo bilan forward qilingan xabar URL sini olish
    res.status(400).json({
        error: 'Bu fayl 20MB dan katta. getFile ishlamaydi.',
        hint: 'Faylni 20MB dan kichik qilib siqing yoki bot premium xarid qiling.'
    });
}

// Health check
app.get('/', (req, res) => res.json({ status: 'ok', service: 'Kino Stream Server' }));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Stream server ${PORT} portda ishlamoqda`));
