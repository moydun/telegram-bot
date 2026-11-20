import html

from aiohttp import web

from db import DB

PAGE = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Просмотр</title>
<style>
 html,body{{margin:0;height:100%;background:#0b0b0c;color:#eee;font:14px/1.4 system-ui}}
 .wrap{{position:fixed;inset:0;display:grid;grid-template-rows:1fr auto}}
 iframe{{width:100%;height:100%;border:0}}
 .bar{{display:flex;gap:8px;padding:8px 12px;align-items:center}}
 .bar b{{font-weight:600}}
 a{{color:#7ab8ff;text-decoration:none}}
</style></head>
<body><div class="wrap">
<iframe src="{url}" allow="autoplay; fullscreen; encrypted-media; picture-in-picture"
        allowfullscreen referrerpolicy="origin"></iframe>
<div class="bar"><b>{label}</b><a href="{url}" target="_blank" rel="noopener">Открыть в браузере</a></div>
</div></body></html>"""


def build(db: DB) -> web.Application:
    app = web.Application()

    async def play(request: web.Request) -> web.Response:
        try:
            source_id = int(request.match_info["id"])
        except ValueError:
            raise web.HTTPNotFound
        src = await db.get_source(source_id)
        if not src:
            raise web.HTTPNotFound(text="Источник удалён")
        await db.mark_ok(source_id)
        label = " / ".join(filter(None, [src["translation"], src["quality"]])) or src["provider"]
        return web.Response(
            text=PAGE.format(url=html.escape(src["url"], quote=True), label=html.escape(label)),
            content_type="text/html",
        )

    app.router.add_get("/play/{id}", play)
    app.router.add_get("/healthz", lambda _: web.Response(text="ok"))
    return app