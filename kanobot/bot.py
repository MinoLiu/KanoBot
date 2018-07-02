import discord
import asyncio
import logging
import sys
import colorlog
import inspect
import traceback
import aiohttp
import random

from copy import deepcopy
from datetime import datetime

from functools import wraps
from textwrap import dedent

from tweepy.api import API
from tweepy import Stream
from .twitter import StdOutListener

from . import exceptions
from .config import Config, ConfigDefaults
from .constructs import Response
from .constants import DISCORD_MSG_CHAR_LIMIT
from .jsonIO import JsonIO

LOG = logging.getLogger(__name__)


def _get_variable(name):
    stack = inspect.stack()
    try:
        for frames in stack:
            try:
                frame = frames[0]
                current_locals = frame.f_locals
                if name in current_locals:
                    return current_locals[name]
            finally:
                del frame
    finally:
        del stack


class Bot(discord.Client):
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = ConfigDefaults.config_file
        self.config = Config(config_file)
        self.jsonIO = JsonIO()

        self.cached_app_info = None
        self.exit_signal = None
        self.init_ok = False
        self.timeout = self.config.timeout
        self.twitter = None
        self.twitter_listener = None
        self.twitter_stream = None

        self._setup_logging()
        super().__init__()
        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.http.user_agent += ' Kanobot'
        self.colors = [0x7f0000, 0x535900, 0x40d9ff, 0x8c7399, 0xd97b6c, 0xf2ff40, 0x8fb6bf, 0x502d59, 0x66504d,
                       0x89b359, 0x00aaff, 0xd600e6, 0x401100, 0x44ff00, 0x1a2b33, 0xff00aa, 0xff8c40, 0x17330d,
                       0x0066bf, 0x33001b, 0xb39886, 0xbfffd0, 0x163a59, 0x8c235b, 0x8c5e00, 0x00733d, 0x000c59,
                       0xffbfd9, 0x4c3300, 0x36d98d, 0x3d3df2, 0x590018, 0xf2c200, 0x264d40, 0xc8bfff, 0xf23d6d,
                       0xd9c36c, 0x2db3aa, 0xb380ff, 0xff0022, 0x333226, 0x005c73, 0x7c29a6]

    def __del__(self):
        # These functions return futures but it doesn't matter
        try:
            self.http.close()
        except:
            pass

        try:
            self.aiosession.close()
        except:
            pass

        super().__init__()
        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.http.user_agent += ' Kanobot'

    def _cleanup(self):
        try:
            self.loop.run_until_complete(self.logout())
        except:
            pass

        pending = asyncio.Task.all_tasks()
        gathered = asyncio.gather(*pending)

        try:
            gathered.cancel()
            self.loop.run_until_complete(gathered)
            gathered.exception()
        except:
            pass

    def _setup_logging(self):
        if len(logging.getLogger(__package__).handlers) >= 1:
            LOG.debug("Skipping logger setup, already setup")
            return

        shandler = logging.StreamHandler(stream=sys.stdout)
        shandler.setFormatter(colorlog.LevelFormatter(
            fmt={
                'DEBUG': '{log_color}[{levelname}:{module}] {message}',
                'INFO': '{log_color}{message}',
                'WARNING': '{log_color}{levelname}: {message}',
                'ERROR': '{log_color}[{levelname}:{module}] {message}',
                'CRITICAL': '{log_color}[{levelname}:{module}] {message}',

                'EVERYTHING': '{log_color}[{levelname}:{module}] {message}',
                'NOISY': '{log_color}[{levelname}:{module}] {message}',
                'VOICEDEBUG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}',
                'FFMPEG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}'
            },
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'white',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'bold_red',

                'EVERYTHING': 'white',
                'NOISY':      'white',
                'FFMPEG':     'bold_purple',
                'VOICEDEBUG': 'purple',
            },
            style='{',
            datefmt=''
        ))
        logging.getLogger(__package__).setLevel(logging.DEBUG)
        shandler.setLevel(self.config.debug_level)
        fh = logging.FileHandler(filename='logs/kanobot.log', encoding='utf-8', mode='w')
        fh.setLevel(self.config.debug_level)
        logging.getLogger(__package__).addHandler(fh)
        logging.getLogger(__package__).addHandler(shandler)
        LOG.debug("Set logging level to %s", self.config.debug_level_str)
        if self.config.debug_mode:
            dlogger = logging.getLogger('discord')
            dlogger.setLevel(logging.DEBUG)
            dhandler = logging.FileHandler(
                filename='logs/discord.log', encoding='utf-8', mode='w')
            dhandler.setFormatter(logging.Formatter(
                '{asctime}:{levelname}:{name}: {message}', style='{'))
            dlogger.addHandler(dhandler)

    def _gen_embed(self):
        """ Provides a basic template for embeds"""
        e = discord.Embed()
        e.colour = random.choice(self.colors)
        e.set_footer(text='© ({})'.format(self.user.name),
                     icon_url=self.user.avatar_url)
        e.set_author(name=self.user.name,
                     icon_url=self.user.avatar_url)
        e.timestamp = datetime.utcnow()
        return e

    async def _cache_app_info(self, *, update=False):
        if not self.cached_app_info and not update and self.user.bot:
            LOG.debug("Caching app info")
            self.cached_app_info = await self.application_info()
        return self.cached_app_info

    # pylint: disable=E0213
    # pylint: disable=E1102
    def ensure_appinfo(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            await self._cache_app_info()
            # noinspection PyCallingNonCallable
            return await func(self, *args, **kwargs)
        return wrapper

    @ensure_appinfo
    async def _on_ready_sanity_checks(self):
        # config async validate
        await self._scheck_configs()

    @ensure_appinfo
    async def generate_invite_link(self,
                                   *,
                                   permissions=discord.Permissions(70380544),
                                   guild=None):
        """ TODO """
        return discord.utils.oauth_url(
            self.cached_app_info.id, permissions=permissions, guild=guild)

    async def _scheck_configs(self):
        LOG.debug("Validating config")
        await self.config.async_validate(self)
        self.config.validate_twitter()
        if self.config.twitter_auth:
            await self._start_twitter()

    async def _start_twitter(self):
        data = self.jsonIO.get(self.config.webhook_file)
        self.twitter = API(self.config.twitter_auth)
        self.twitter_listener = StdOutListener(data)
        self.twitter_stream = Stream(
            self.config.twitter_auth, self.twitter_listener, retry_420=10)
        if data.get('twitter_ids', []):
            self.twitter_stream.filter(
                list(set(data.get('twitter_ids'))), None, True)

    async def _reload_twitter(self):
        data = self.jsonIO.get(self.config.webhook_file)
        self.twitter_listener.reset(data)
        self.twitter_stream.disconnect()
        await asyncio.sleep(10)
        del self.twitter_stream
        self.twitter_stream = Stream(
            self.config.twitter_auth, self.twitter_listener, retry_420=10)
        if data.get('twitter_ids', []):
            self.twitter_stream.filter(
                list(set(data.get('twitter_ids'))), None, True)

    def _get_owner(self, *, guild=None):
        return discord.utils.find(
            lambda m: m.id == self.config.owner_id,
            guild.members if guild else self.get_all_members())

    async def safe_send_message(self, dest, content, **kwargs):
        tts = kwargs.pop('tts', False)
        quiet = kwargs.pop('quiet', False)
        expire_in = kwargs.pop('expire_in', 0)
        allow_none = kwargs.pop('allow_none', True)
        also_delete = kwargs.pop('also_delete', None)

        msg = None
        lfunc = LOG.debug if quiet else LOG.warning

        try:
            if content is not None or allow_none:
                if isinstance(content, discord.Embed):
                    msg = await dest.send(embed=content)
                else:
                    msg = await dest.send(content, tts=tts)

        except discord.Forbidden:
            lfunc("Cannot send message to \"%s\", no permission", dest.name)

        except discord.NotFound:
            lfunc("Cannot send message to \"%s\", invalid channel?", dest.name)

        except discord.HTTPException:
            if len(content) > DISCORD_MSG_CHAR_LIMIT:
                lfunc("Message is over the message size limit (%s)",
                      DISCORD_MSG_CHAR_LIMIT)
            else:
                lfunc("Failed to send message")
                LOG.noise(
                    "Got HTTPException trying to send message to %s: %s", dest, content)

        finally:
            if msg and expire_in:
                asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

            if also_delete and isinstance(also_delete, discord.Message):
                asyncio.ensure_future(
                    self._wait_delete_msg(also_delete, expire_in))

        return msg

    async def _wait_delete_msg(self, message, after):
        await asyncio.sleep(after)
        await self.safe_delete_message(message, quiet=True)

    async def safe_delete_message(self, message, *, quiet=False):
        lfunc = LOG.debug if quiet else LOG.warning

        try:
            return await message.delete()

        except discord.Forbidden:
            lfunc("Cannot delete message \"{}\", no permission".format(
                message.clean_content))

        except discord.NotFound:
            lfunc("Cannot delete message \"{}\", message not found".format(
                message.clean_content))

    async def safe_edit_message(self, message, new, *, send_if_fail=False, quiet=False):
        lfunc = LOG.debug if quiet else LOG.warning

        try:
            return await message.edit(new)

        except discord.NotFound:
            lfunc("Cannot edit message \"{}\", message not found".format(
                message.clean_content))
            if send_if_fail:
                lfunc("Sending message instead")
                return await self.safe_send_message(message.channel, new)

    async def send_typing(self, destination):
        try:
            return await destination.trigger_typing()
        except discord.Forbidden:
            LOG.warning(
                "Could not send typing to {}, no permission".format(destination))

    async def on_ready(self):
        dlogger = logging.getLogger('discord')
        for handler in dlogger.handlers:
            if getattr(handler, 'terminator', None) == '':
                dlogger.removeHandler(handler)
                print()

        LOG.debug("Connection established, ready to go.")

        self.ws._keep_alive.name = 'Gateway Keepalive'

        if self.init_ok:
            LOG.debug(
                "Received additional READY event, may have failed to resume")
            return

        await self._on_ready_sanity_checks()
        print()

        LOG.info('Connected!   -   KanoBot\n')

        self.init_ok = True

        ################################

        LOG.info("Bot:   {0}/{1}#{2}{3}".format(
            self.user.id,
            self.user.name,
            self.user.discriminator,
            ' [BOT]' if self.user.bot else ' [Userbot]'
        ))

        owner = self._get_owner()
        if owner and self.guilds:
            LOG.info("Owner: {0}/{1}#{2}\n".format(
                owner.id,
                owner.name,
                owner.discriminator
            ))

            LOG.info('Server List:')
            [LOG.info(' - ' + s.name) for s in self.guilds]

        elif self.guilds:
            LOG.warning(
                "Owner could not be found on any server (id: %s)\n",
                self.config.owner_id)

            LOG.info('Server List:')
            [LOG.info(' - ' + s.name) for s in self.guilds]

        else:
            LOG.warning("Owner unknown, bot is not on any servers.")
            if self.user.bot:
                LOG.warning(
                    """To make the bot join a server,
                    paste this link in your browser. \n
                    Note: You should be logged into your main account
                    and have \n
                    manage server permissions on the server you want
                    the bot to join.\n"""
                    "  " + await self.generate_invite_link()
                )

        print(flush=True)
        LOG.info("Options:")

        LOG.info("  Command prefix: " + self.config.command_prefix)
        LOG.info("  Delete Messages: " +
                 ['Disabled', 'Enabled'][self.config.delete_messages])
        if self.config.delete_messages:
            LOG.info("  Delete Invoking: " +
                     ['Disabled', 'Enabled'][self.config.delete_invoking])
        LOG.info("  Debug Mode: " +
                 ['Disabled', 'Enabled'][self.config.debug_mode])
        LOG.info("  Debug Level: " + self.config.debug_level_str)
        LOG.info("  Twitter: {}".format(
            "Enabled" if self.config.twitter_auth else "Disabled"))
        print(flush=True)

    async def on_message(self, message):
        await self.wait_until_ready()

        if message.channel.id in self.config.block_channels:
            return

        message_content = message.content.strip()

        if not message_content.startswith(self.config.command_prefix):
            return

        if message.author == self.user:
            LOG.warning(
                "Ignoring command from myself (%s)", message.content)
            return

        command, *args = message_content.split(' ')
        command = command[len(self.config.command_prefix):].lower().strip()
        handler = getattr(self, 'cmd_' + command, None)
        if not handler:
            return

        private_msg_list = ['joinserver', 'ban',
                            'setavatar', 'restart', 'help']
        if isinstance(message.channel, discord.DMChannel):
            if not (message.author.id == self.config.owner_id and
                    command in private_msg_list):
                await message.channel.send(
                    'You cannot use this bot in private messages.')
                return

        LOG.info("{0.id}/{0!s}: {1}".format(message.author, message_content
                                            .replace('\n', '\n... ')))
        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()

        sentmsg = response = None

        try:
            handler_kwargs = {}
            if params.pop('message', None):
                handler_kwargs['message'] = message

            if params.pop('channel', None):
                handler_kwargs['channel'] = message.channel

            if params.pop('guild', None):
                handler_kwargs['guild'] = message.guild

            if params.pop('author', None):
                handler_kwargs['author'] = message.author

            if params.pop('user_mentions', None):
                handler_kwargs['user_mentions'] = list(
                    map(message.guild.get_member, message.raw_mentions))

            if params.pop('channel_mentions', None):
                handler_kwargs['channel_mentions'] = list(
                    map(message.guild.get_channel, message.raw_channel_mentions))

            if params.pop('leftover_args', None):
                handler_kwargs['leftover_args'] = args

            args_expected = []

            for key, param in list(params.items()):
                # parse (*args) as a list of args
                if param.kind == param.VAR_POSITIONAL:
                    handler_kwargs[key] = args
                    params.pop(key)
                    continue

                # parse (*, args) as args rejoined as a string
                # multiple of these arguments will have the same value
                if param.kind == param.KEYWORD_ONLY and param.default == param.empty:
                    handler_kwargs[key] = ' '.join(args)
                    params.pop(key)
                    continue

                doc_key = '[{}={}]'.format(
                    key, param.default) if param.default is not param.empty else key
                args_expected.append(doc_key)

                # Ignore keyword args with default values when the command had no arguments
                if not args and param.default is not param.empty:
                    params.pop(key)
                    continue

                # Assign given values to positional arguments
                if args:
                    arg_value = args.pop(0)
                    handler_kwargs[key] = arg_value
                    params.pop(key)

            # Invalid usage, return docstring
            if params:
                docs = getattr(handler, '__doc__', None)
                if not docs:
                    docs = 'Usage: {}{} {}'.format(
                        self.config.command_prefix,
                        command,
                        ' '.join(args_expected)
                    )

                docs = dedent(docs)
                text = '```\n{}\n```'.format(docs.format(
                    command_prefix=self.config.command_prefix))
                if self.config.embeds:
                    content = self._gen_embed()
                    content.title = command
                    content.description = text
                else:
                    content = text
                await self.safe_send_message(
                    message.channel,
                    content,
                    expire_in=60
                )
                return

            await self.send_typing(message.channel)
            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                if not isinstance(response.content, discord.Embed) and self.config.embeds and response.embed:
                    content = self._gen_embed()
                    content.title = command
                    content.description = response.content
                else:
                    content = response.content

                if response.reply:
                    if isinstance(content, discord.Embed):
                        content.description = '{} {}'.format(
                            message.author.mention, content.description if content.description is not discord.Embed.Empty else '')
                    else:
                        content = '{}: {}'.format(
                            message.author.mention, content)

                sentmsg = await self.safe_send_message(
                    message.channel, content,
                    expire_in=response.delete_after if self.config.delete_messages else 0,
                    also_delete=message if self.config.delete_invoking else None)

        except (exceptions.CommandError, exceptions.HelpfulError) as e:
            LOG.error("Error in {0}: {1.__class__.__name__}: {1.message}".format(
                command, e), exc_info=True)
            expirein = e.expire_in if self.config.delete_messages else None
            alsodelete = message if self.config.delete_invoking else None

            if self.config.embeds:
                content = self._gen_embed()
                content.add_field(name='Error', value=e.message, inline=False)
                content.colour = 13369344
            else:
                content = '```\n{}\n```'.format(e.message)

            await self.safe_send_message(
                message.channel,
                content,
                expire_in=expirein,
                also_delete=alsodelete
            )
        except exceptions.Signal:
            raise
        except Exception:
            LOG.error("Exception in on_message", exc_info=True)
            if self.config.debug_mode:
                await self.safe_send_message(message.channel, '```\n{}\n```'.format(traceback.format_exc()))

        finally:
            if not sentmsg and not response and self.config.delete_invoking:
                await asyncio.sleep(5)
                await self.safe_delete_message(message, quiet=True)

    async def logout(self):
        return await super().logout()

    async def restart(self):
        """ TODO """
        self.exit_signal = exceptions.RestartSignal
        await self.logout()

    def run(self):
        try:
            self.loop.run_until_complete(self.start(*self.config.auth))

        except discord.errors.LoginFailure:
            # Add if token, else
            raise exceptions.HelpfulError(
                "Bot cannot login, bad credentials.",
                "Fix your %s in the config.ini file.  "
                "Remember that each field should be on their own line."
                % ['Token', 'Credentials'][len(self.config.auth)]
            )  # ^^^^ In theory self.config.auth should never have no items
        finally:
            try:
                self._cleanup()
            except Exception:
                LOG.error("Error in cleanup", exc_info=True)

            self.loop.close()
            # pylint: disable=E0702
            if self.exit_signal:
                raise self.exit_signal


class Kanobot(Bot):
    def __init__(self, config_file=None):
        super().__init__(config_file)

    # pylint: disable=E0213
    # pylint: disable=E1102
    def owner_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Only allow the owner to use these commands
            orig_msg = _get_variable('message')

            if not orig_msg or orig_msg.author.id == self.config.owner_id:
                # noinspection PyCallingNonCallable
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError(
                    "only the owner can use this command", expire_in=30)
        wrapper.owner_cmd = True
        return wrapper

    def admin_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Only allow the admin to use these commands
            orig_msg = _get_variable('message')

            if orig_msg.author.id in self.config.admin_ids:
                # noinspection PyCallingNonCallable
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError(
                    "only admin users can use this command", expire_in=30)
        wrapper.admin_cmd = True
        return wrapper

    def dev_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            orig_msg = _get_variable('message')

            if orig_msg.author.id in self.config.dev_ids:
                # noinspection PyCallingNonCallable
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError(
                    "only dev users can use this command", expire_in=30)
        wrapper.dev_cmd = True
        return wrapper

    def require_twitter(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            if not self.twitter:
                raise exceptions.HelpfulError(
                    'Twitter feature are disabled!',
                    "Go to https://apps.twitter.com\n"
                    "ConsumerKey, ConsumerSecret, AccessToken, AccessTokenSecret\n"
                    "Make sure they are correct and fill into config.ini\n", expire_in=30)
            return await func(self, *args, **kwargs)
        return wrapper

    @admin_only
    async def cmd_joinserver(self, message, server_link=None):
        """
        Usage:
            {command_prefix}joinserver invite_link
        Asks the bot to join a server.
        Note: Bot accounts cannot use invite links.
        """

        if self.user.bot:
            url = await self.generate_invite_link()
            return Response(
                """Bot accounts can't use invite links!\n
                Click here to add me to a server: \n{}""".format(url),
                reply=True,
                delete_after=0
            )

    @admin_only
    async def cmd_purge(self, message, channel, author, user_mentions, search_range=50, user=None):
        """
        Usage:
            {command_prefix}purge range [user]
        Removes up to [range] messages the bot has posted in chat.
        Default: 50, Max: 1000
        e.g. {command_prefix}purge
             {command_prefix}purge 80
        user is optionaly, must be string or @name
        e.g. {command_prefix}purge 30 bots
        """
        try:
            float(search_range)  # lazy check
            search_range = min(int(search_range), 1000)
        except:
            return Response("Enter a number.  NUMBER.  That means digits. `15`.  Etc.", reply=True, delete_after=8)

        def check_user(m):
            if m.pinned:
                return False

            if not user_mentions:
                return m.author.name == user if user else True
            else:
                for u in user_mentions:
                    if m.author == u:
                        return True
                return False
        deleted = await channel.purge(limit=search_range, check=check_user, bulk=True)
        return Response('successfully deleted {} messages from this channel!'.format(len(deleted)), reply=True, delete_after=8)

    @admin_only
    async def cmd_restart(self, channel):
        """
        Usage:
            {command_prefix}restart
        restart the bot
        """
        msg = await self.safe_send_message(channel, "\N{WAVING HAND SIGN} Restarting.")
        await asyncio.sleep(3)
        await self.safe_delete_message(msg)
        self.exit_signal = exceptions.RestartSignal()
        await self.logout()

    @owner_only
    async def cmd_setname(self, leftover_args, name):
        """
        Usage:
            {command_prefix}setname name
        Changes the bot's username.
        Note: This operation is limited by discord to twice per hour.
        """

        name = ' '.join([name, *leftover_args])

        try:
            await self.user.edit(username=name)

        except discord.HTTPException:
            raise exceptions.CommandError(
                "Failed to change name. Did you change names too many times? "
                "Remember name changes are limited to twice per hour.", expire_in=20)

        except Exception as e:
            raise exceptions.CommandError(e, expire_in=20)

        return Response("\n:ok_hand:", delete_after=20)

    @owner_only
    async def cmd_setavatar(self, message, url=None):
        """
        Usage:
            {command_prefix}setavatar [url]
        Changes the bot's avatar.
        Attaching a file and leaving the url parameter blank also works.
        """
        if message.attachments:
            thing = message.attachments[0].url
        elif url:
            thing = url.strip('<>')
        else:
            return Response("```\n{}```".format(
                dedent(self.cmd_setavatar.__doc__).format(
                    command_prefix=self.config.command_prefix)),
                reply=True, delete_after=30)

        try:
            async with self.aiosession.get(thing, timeout=self.timeout) as res:
                await self.user.edit(avatar=await res.read())

        except Exception as error:
            raise exceptions.CommandError(
                "Unable to change avatar: {}".format(error), expire_in=20)

        return Response("\n:ok_hand:", delete_after=20)

    async def cmd_id(self, author, user_mentions):
        """
        Usage:
            {command_prefix}id [@user]
        Tells the user their id or the id of another user.
        """
        if not user_mentions:
            return Response('Your ID is `{0}`'.format(author.id), reply=True, delete_after=35)
        else:
            usr = user_mentions[0]
            return Response('**{0}**\'s ID is `{1}`'.format(usr.name, usr.id), reply=True, delete_after=35)

    async def cmd_help(self, author, command=None):
        """
        Usage:
            {command_prefix}help
            {command_prefix}help [command]
        Prints a help message.
        If a command is specified, it prints a help message for that command.
        Otherwise, it lists the available commands.
        """

        if command:
            cmd = getattr(self, 'cmd_' + command, None)
            if cmd and not hasattr(cmd, 'dev_cmd'):
                return Response(
                    "```\n{}```".format(
                        dedent(cmd.__doc__)
                    ).format(command_prefix=self.config.command_prefix),
                    delete_after=60
                )
            else:
                return Response("No such command", delete_after=10)

        else:
            helpmsg = "**Available commands**\n```"
            commands = []

            for att in dir(self):
                if att.startswith('cmd_') and att != 'cmd_help' \
                        and not hasattr(getattr(self, att), 'dev_cmd') \
                        and not hasattr(getattr(self, att), 'admin_cmd') \
                        and not hasattr(getattr(self, att), 'owner_cmd'):
                    command_name = att.replace('cmd_', '').lower()
                    commands.append("{}{}".format(
                        self.config.command_prefix, command_name))
                elif att.startswith('cmd_') and att != 'cmd_help' \
                        and author.id in self.config.admin_ids \
                        and hasattr(getattr(self, att), 'admin_cmd'):
                    command_name = att.replace('cmd_', '').lower()
                    commands.append("{}{}".format(
                        self.config.command_prefix, command_name))
                elif att.startswith('cmd_') and att != 'cmd_help' \
                        and author.id == self.config.owner_id \
                        and hasattr(getattr(self, att), 'owner_cmd'):
                    command_name = att.replace('cmd_', '').lower()
                    commands.append("{}{}".format(
                        self.config.command_prefix, command_name))
            commands.sort()
            helpmsg += ", ".join(commands)
            helpmsg += "```\n\nYou can use `{}help x` for more info about each command." \
                .format(self.config.command_prefix)
        return Response(helpmsg, reply=True)

    @admin_only
    @require_twitter
    async def cmd_set_twitter(self, guild, action, name, new_channel_name=None, includeReplyToUser=None, includeUserReply=None, includeRetweet=None):
        """
        Usage:
            {command_prefix}set_twitter [+, -] [name] | optional [new_channel_name] [includeReplyToUser] [includeUserReply] [includeRetweet]
            {command_prefix}set_twitter + [name]
            {command_prefix}set_twitter + [name] [new_channel_name] True True True
            {command_prefix}set_twitter - [name]
        Add webhook to subscribe twitter user status
        """
        actions = ['+', '-']
        if action not in actions:
            return Response('Invalid action must be + or - ', reply=True, delete_after=10)
        if new_channel_name and (len(new_channel_name) > 32 or len(new_channel_name) < 2):
            return Response('Invalid channel name, Must be between 2 and 32 in length', reply=True, delete_after=20)

        if includeReplyToUser is not None:
            includeReplyToUser = True
        else:
            includeReplyToUser = False

        if includeUserReply is not None:
            includeUserReply = True
        else:
            includeUserReply = False

        if includeRetweet is not None:
            includeRetweet = True
        else:
            includeRetweet = False

        try:
            user_obj = self.twitter.get_user(name)
        except Exception:
            return Response('Invalid twitter id, name. e.g. @kano_2525 or kano_2525', reply=True)

        data = self.jsonIO.get(self.config.webhook_file)
        if not data.get('Discord', None):
            data['Discord'] = []
            data['twitter_ids'] = []
            data['Category_ids'] = {}

        category_id = data['Category_ids'].get(str(guild.id), None)

        subscribed = False
        for subscribe in data['Discord']:
            if subscribe['guild_id'] != guild.id:
                continue

            if subscribe['twitter_id'] == user_obj.id_str:
                subscribed = subscribe

        if action == '+':
            if subscribed:
                return Response('Already subscribed \n{}\n'.format(user_obj.name))

            channel_name = "{}".format(
                user_obj.screen_name) if new_channel_name is None else new_channel_name

            try:
                if category_id is None or guild.get_channel(category_id) is None:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(
                            send_messages=False)
                    }
                    data['Category_ids'][str(guild.id)] = category_id = (await guild.create_category_channel('twitter', overwrites=overwrites)).id

                category = guild.get_channel(category_id)

                channel = (await guild.create_text_channel(
                    channel_name, category=category))

            except Exception:
                raise exceptions.CommandError(
                    "Create channel {} failed".format(channel_name), expire_in=30)

            try:
                webhook_obj = await channel.create_webhook(name=channel_name)
            except Exception as e:
                raise exceptions.CommandError(e, expire_in=30)

            data['Discord'].append({
                'guild_id': guild.id,
                'channel_id': channel.id,
                'webhook_url': webhook_obj.url,
                'webhook_id': webhook_obj.id,
                'twitter_id': user_obj.id_str,
                'includeReplyToUser': includeReplyToUser,
                'includeUserReply': includeUserReply,
                'includeRetweet': includeRetweet})
            data['twitter_ids'].append(user_obj.id_str)
            data['twitter_ids'] = data['twitter_ids']
            self.jsonIO.save(self.config.webhook_file, data)
        else:
            if not subscribed:
                return Response('{} did not subscribe'.format(user_obj.name))
            data['Discord'].remove(subscribed)
            data['twitter_ids'].remove(subscribed['twitter_id'])
            try:
                # await (await self.get_webhook_info(subscribe['webhook_id'])).delete()
                await guild.get_channel(subscribed['channel_id']).delete()
            except Exception:
                raise exceptions.CommandError(
                    'Delete channel failed', expire_in=20)
            self.jsonIO.save(self.config.webhook_file, data)

        await self._reload_twitter()
        return Response("{} :ok_hand:\n\n{}\n".format("Subscribe" if action == '+' else "Unsubscribe", user_obj.name))

    @admin_only
    @require_twitter
    async def cmd_reload_twitter(self):
        """
        Usage:
            {command_prefix}reload_twitter
        This command is for reloaded twitter Streaming
        """
        await self._reload_twitter()
        return Response(':ok_hand:\n Reload success')

    @admin_only
    async def cmd_kick(self, user_mentions):
        """
        Usage:
            {command_prefix}kick @user
        Kick user from server.
        """
        users = []
        for user in user_mentions:
            await user.kick()
            users.append(user.name)

        return Response('successfully kicked {} from this server!'.format(", ".join(users)))
