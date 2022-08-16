import asyncio
import asyncio.tasks
import datetime
import functools
import ipaddress
import itertools
import typing
import logging
from typing import Dict, List, Optional, Union

from aiohttp import web
from aiohttp.web_exceptions import HTTPGone

from aiogram import types
from aiogram.bot import api
from aiogram.types import ParseMode
from aiogram.types.base import Boolean, Float, Integer, String
from aiogram.utils import helper, markdown
from aiogram.utils import json
from aiogram.utils.deprecated import warn_deprecated as warn
from aiogram.utils.exceptions import TimeoutWarning
from aiogram.utils.payload import prepare_arg

DEFAULT_WEB_PATH = '/webhook'
DEFAULT_ROUTE_NAME = 'webhook_handler'
BOT_DISPATCHER_KEY = 'BOT_DISPATCHER'

RESPONSE_TIMEOUT = 55

WEBHOOK = 'webhook'
WEBHOOK_CONNECTION = 'WEBHOOK_CONNECTION'
WEBHOOK_REQUEST = 'WEBHOOK_REQUEST'

TELEGRAM_SUBNET_1 = ipaddress.IPv4Network('149.154.160.0/20')
TELEGRAM_SUBNET_2 = ipaddress.IPv4Network('91.108.4.0/22')

allowed_ips = set()

log = logging.getLogger(__name__)


def _check_ip(ip: str) -> bool:
    """
    Check IP in range

    :param ip:
    :return:
    """
    address = ipaddress.IPv4Address(ip)
    return address in allowed_ips


def allow_ip(*ips: typing.Union[str, ipaddress.IPv4Network, ipaddress.IPv4Address]):
    """
    Allow ip address.

    :param ips:
    :return:
    """
    for ip in ips:
        if isinstance(ip, ipaddress.IPv4Address):
            allowed_ips.add(ip)
        elif isinstance(ip, str):
            allowed_ips.add(ipaddress.IPv4Address(ip))
        elif isinstance(ip, ipaddress.IPv4Network):
            allowed_ips.update(ip.hosts())
        else:
            raise ValueError(f"Bad type of ipaddress: {type(ip)} ('{ip}')")


# Allow access from Telegram servers
allow_ip(TELEGRAM_SUBNET_1, TELEGRAM_SUBNET_2)


class CustomWebhookRequestHandler(web.View):
    """
    Simple Webhook request handler for aiohttp web server.

    You need to register that in app:

    .. code-block:: python3

        app.router.add_route('*', '/your/webhook/path', WebhookRequestHandler, name='webhook_handler')

    But first you need to configure application for getting Dispatcher instance from request handler!
    It must always be with key 'BOT_DISPATCHER'

    .. code-block:: python3

        bot = Bot(TOKEN, loop)
        dp = Dispatcher(bot)
        app['BOT_DISPATCHER'] = dp

    """

    def get_dispatcher(self):
        """
        Get Dispatcher instance from environment

        :return: :class:`aiogram.Dispatcher`
        """
        dp = self.request.app[BOT_DISPATCHER_KEY]
        try:
            from aiogram import Bot, Dispatcher
            Dispatcher.set_current(dp)
            Bot.set_current(dp.bot)
        except RuntimeError:
            pass
        return dp

    async def parse_update(self, bot):
        """
        Read update from stream and deserialize it.

        :param bot: bot instance. You an get it from Dispatcher
        :return: :class:`aiogram.types.Update`
        """
        data = await self.request.json()
        return types.Update(**data)

    async def post(self):
        """
        Process POST request

        if one of handler returns instance of :class:`aiogram.dispatcher.webhook.BaseResponse` return it to webhook.
        Otherwise do nothing (return 'ok')

        :return: :class:`aiohttp.web.Response`
        """
        self.validate_ip()

        # context.update_state({'CALLER': WEBHOOK,
        #                       WEBHOOK_CONNECTION: True,
        #                       WEBHOOK_REQUEST: self.request})

        dispatcher = self.get_dispatcher()
        update = await self.parse_update(dispatcher.bot)
        
        logging.warning('update: ' + str(update))

        try:
            results = await self.process_update(update)
            response = self.get_response(results)
            logging.warning('results: ' + str(results))
            logging.warning('response: ' + str(response))
        except:
            response = None

        if response:
            web_response = response.get_web_response()
            logging.warning('web responce: ' + str(web_response))
        else:
            web_response = web.Response(text='ok')
            logging.warning('web responce: ' + str(web_response))

        if self.request.app.get('RETRY_AFTER', None):
            web_response.headers['Retry-After'] = str(self.request.app['RETRY_AFTER'])

        return web_response

    async def get(self):
        self.validate_ip()
        return web.Response(text='')

    async def head(self):
        self.validate_ip()
        return web.Response(text='')

    async def process_update(self, update):
        """
        Need respond in less than 60 seconds in to webhook.

        So... If you respond greater than 55 seconds webhook automatically respond 'ok'
        and execute callback response via simple HTTP request.

        :param update:
        :return:
        """

        dispatcher = self.get_dispatcher()
        loop = asyncio.get_event_loop()

        # Analog of `asyncio.wait_for` but without cancelling task
        waiter = loop.create_future()
        timeout_handle = loop.call_later(RESPONSE_TIMEOUT, asyncio.tasks._release_waiter, waiter)
        cb = functools.partial(asyncio.tasks._release_waiter, waiter)

        fut = asyncio.ensure_future(dispatcher.updates_handler.notify(update))
        fut.add_done_callback(cb)

        try:
            try:
                await waiter
            except asyncio.CancelledError:
                fut.remove_done_callback(cb)
                fut.cancel()
                raise

            if fut.done():
                return fut.result()
            # context.set_value(WEBHOOK_CONNECTION, False)
            fut.remove_done_callback(cb)
            fut.add_done_callback(self.respond_via_request)
        finally:
            timeout_handle.cancel()

    def respond_via_request(self, task):
        """
        Handle response after 55 second.

        :param task:
        :return:
        """
        warn(f"Detected slow response into webhook. "
             f"(Greater than {RESPONSE_TIMEOUT} seconds)\n"
             f"Recommended to use 'async_task' decorator from Dispatcher for handler with long timeouts.",
             TimeoutWarning)

        dispatcher = self.get_dispatcher()
        loop = asyncio.get_running_loop()

        try:
            results = task.result()
        except Exception as e:
            loop.create_task(
                dispatcher.errors_handlers.notify(dispatcher, types.Update.get_current(), e))
        else:
            response = self.get_response(results)
            if response is not None:
                asyncio.ensure_future(response.execute_response(dispatcher.bot))

    def get_response(self, results):
        """
        Get response object from results.

        :param results: list
        :return:
        """
        if results is None:
            return None
        for result in itertools.chain.from_iterable(results):
            if isinstance(result, BaseResponse):
                return result

    def check_ip(self):
        """
        Check client IP. Accept requests only from telegram servers.

        :return:
        """
        # For reverse proxy (nginx)
        forwarded_for = self.request.headers.get('X-Forwarded-For', None)
        if forwarded_for:
            # get the left-most ip when there is multiple ips (request got through multiple proxy/load balancers)
            forwarded_for = forwarded_for.split(",")[0]
            return forwarded_for, _check_ip(forwarded_for)

        # For default method
        peer_name = self.request.transport.get_extra_info('peername')
        if peer_name is not None:
            host, _ = peer_name
            return host, _check_ip(host)

        # Not allowed and can't get client IP
        return None, False

    def validate_ip(self):
        """
        Check ip if that is needed. Raise web.HTTPUnauthorized for not allowed hosts.
        """
        if self.request.app.get('_check_ip', False):
            ip_address, accept = self.check_ip()
            if not accept:
                log.warning(f"Blocking request from an unauthorized IP: {ip_address}")
                raise web.HTTPUnauthorized()

            # context.set_value('TELEGRAM_IP', ip_address)