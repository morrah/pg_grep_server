#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import aioredis
import aiohttp_jinja2
import jinja2
from aiohttp import web, WSMsgType as MsgType
from settings import log
import aiohttp_debugtoolbar


class Index(web.View):
    @aiohttp_jinja2.template('index.html')
    async def get(self):
        return {'ip_filter': self.request.transport.get_extra_info('peername')[0]}


class WebSocket(web.View):
    async def get(self):
        ws = web.WebSocketResponse()
        await ws.prepare(self.request)

        self.request.app['websockets'].append(ws)
        log.debug('ws connection incoming')

        async for msg in ws:
            if msg.tp == MsgType.text:
                if msg.data == 'close':
                    await ws.close()
                    break
                elif msg.data.startswith('subscribe'):
                    log.debug('subscribe to redis channel %s' % msg.data)
                    channels = msg.data.split()[1:]
                    with await pool as redis:
                        await redis.connection.execute_pubsub('psubscribe', *channels)
                        tasks = []
                        for channel in channels:
                            channel = redis.connection.pubsub_patterns[channel]
                            tasks.append(self.async_reader(channel, ws))
                        # TODO TOFIX: reading from redis blocks reading from websocket
                        await asyncio.gather(*tasks)
                        tasks.clear()
                        try:
                            await redis.connection.execute_pubsub('punsubscribe', *channels)
                        except aioredis.errors.ConnectionClosedError:
                            pass
            elif msg.tp == MsgType.error:
                log.debug('ws connection closed with exception %s' % ws.exception())
                await ws.close()
                break

        self.request.app['websockets'].remove(ws)
        log.debug('websocket connection closed')

        return ws

    async def async_reader(self, channel, ws):
        while (await channel.wait_message()):
            msg = await channel.get(encoding='utf-8')
            await ws.send_str(msg[1])
            #log.debug('%s: %s' % (channel.name, msg[1]))
            if msg == 'STOP':
                break


async def on_shutdown(app):
    for ws in app['websockets']:
        await ws.close(code=1001, message='Server shutdown')


async def shutdown(server, app, handler, pool):
    server.close()
    await server.wait_closed()
    pool.close()
    await pool.wait_closed()
    await app.shutdown()
    await handler.finish_connections(10.0)
    await app.cleanup()


async def broadcast(app, msg):
    for ws in app['websockets']:
        await ws.send_str(msg)


async def init(loop):
    middle = []
    if DEBUG:
        middle.append(aiohttp_debugtoolbar.middleware)

    app = web.Application(loop=loop, middlewares=middle)
    app['websockets'] = []
    app['redis'] = {} # {}

    if DEBUG:
        aiohttp_debugtoolbar.setup(app)
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates'))

    # route part
    for route in routes:
        app.router.add_route(route[0], route[1], route[2], name=route[3])
    app.router.add_static('/static', 'static', name='static')
    # end route part

    app.on_shutdown.append(on_shutdown)
    handler = app.make_handler()

    pool = await aioredis.create_pool(
        ('127.0.0.1', 6379),
        minsize=1, maxsize=40,
        loop=loop
    )

    serv_generator = loop.create_server(handler, SITE_HOST, SITE_PORT)
    return serv_generator, handler, app, pool


if __name__ == "__main__":
    DEBUG = True
    SITE_HOST = '0.0.0.0'
    SITE_PORT = 8001
    routes = [
        ('GET', '/',        Index,  'main'),
        ('GET', '/ws',      WebSocket, 'log'),
    ]
    
    loop = asyncio.get_event_loop()
    serv_generator, handler, app, pool = loop.run_until_complete(init(loop))
    serv = loop.run_until_complete(serv_generator)
    log.debug('start server')
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.debug(' Stop server begin')
    finally:
        loop.run_until_complete(shutdown(serv, app, handler, pool))
        loop.close()
    log.debug('Stop server end')
