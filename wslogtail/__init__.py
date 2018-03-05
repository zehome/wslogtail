# -*- coding: utf-8 -*-

import os
import sys
import json
import asyncio
import pathlib
import logging
import functools
import asyncio_redis
import websockets
from logging.handlers import RotatingFileHandler
from ansi2html import Ansi2HTMLConverter

READBACK_LEN = 79 * 1000


def get_log_path(logdir, logname):
    rootpath = pathlib.Path(logdir)
    logpath = (rootpath / pathlib.Path(f"{logname}.log")).resolve()
    if (
        os.path.commonpath([rootpath.resolve()]) !=
        os.path.commonpath([rootpath.resolve(), logpath.resolve()])
    ):
        raise ValueError("Please, don't try to escape.")
    return logpath


async def wstail(
        websocket, path, *, logdir,
        redis_host, redis_port, redis_db=0,
        channel="wslogger"):
    logname = path.split("/", 1)[1]
    converter = Ansi2HTMLConverter(inline=True)
    connection = await asyncio_redis.Connection.create(
        host=redis_host, port=redis_port, db=redis_db)
    subscriber = await connection.start_subscribe()
    await subscriber.psubscribe(['{}:*'.format(channel)])
    try:
        logpath = get_log_path(logdir, logname)
    except ValueError:
        logpath = None
    if logpath and logpath.exists():
        with logpath.open(mode="rb") as f:
            f.seek(0, 2)
            maxreadback_len = f.tell()
            f.seek(-min(READBACK_LEN, maxreadback_len), 2)
            data = f.read().decode("utf-8")
            for l in data.splitlines():
                await websocket.send(
                    json.dumps({
                        'name': logname,
                        'line': converter.convert(l, full=False)
                    })
                )
    while True:
        reply = await subscriber.next_published()
        reply_channel = reply.channel.split(":", 1)[1]
        if reply_channel == logname:
            await websocket.send(
                json.dumps({
                    'name': logname,
                    'line': converter.convert(reply.value, full=False)
                })
            )
    connection.close()


async def redistologging(logdir, redis_host, redis_port, redis_db, channel):
    loggers = {}
    rootpath = pathlib.Path(logdir)
    connection = await asyncio_redis.Connection.create(
        host=redis_host, port=redis_port, db=redis_db)
    subscriber = await connection.start_subscribe()
    await subscriber.psubscribe(['{}:*'.format(channel)])
    while True:
        reply = await subscriber.next_published()
        reply_channel = reply.channel.split(":", 1)[1]
        logger = loggers.get(reply_channel, None)
        if not logger:
            logger = logging.getLogger(reply_channel)
            try:
                logpath = get_log_path(logdir, reply_channel)
            except ValueError as e:
                print(e, file=sys.stderr)
                continue
            file_handler = RotatingFileHandler(
                logpath,
                backupCount=1,
                maxBytes=1024 * 1024 * 32)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(file_handler)
            logger.setLevel(logging.INFO)
            loggers[reply_channel] = logger
        logger.info(reply.value)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--logdir", required=True)
    parser.add_argument("--port", default=8756, type=int)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--redis-host", default="localhost")
    parser.add_argument("--redis-port", default=6379)
    parser.add_argument("--redis-db", default=0)
    parser.add_argument("--redis-channel", default="wslogger")
    args = parser.parse_args()

    if not pathlib.Path(args.logdir).exists():
        print("{} does not exists.".format(args.logdir))
        sys.exit(1)

    websocket_server = websockets.serve(
        functools.partial(
            wstail,
            logdir=args.logdir,
            redis_host=args.redis_host,
            redis_port=args.redis_port,
            redis_db=args.redis_db,
            channel=args.redis_channel
        ), args.host, args.port)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(websocket_server)
    loop.run_until_complete(
        redistologging(
            args.logdir,
            redis_host=args.redis_host,
            redis_port=args.redis_port,
            redis_db=args.redis_db,
            channel=args.redis_channel
        )
    )
    loop.run_forever()

if __name__ == "__main__":
    main()
