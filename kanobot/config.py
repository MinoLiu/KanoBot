import os
import sys
import configparser
import shutil
import logging

from .exceptions import HelpfulError

LOG = logging.getLogger(__name__)


class Config:

    def __init__(self, config_file):
        self.config_file = config_file
        self.find_config()

        config = configparser.ConfigParser(interpolation=None)
        config.read(config_file, encoding='utf-8')
        confsections = {"Credentials", "Permissions", "Chat", "Bot"} \
            .difference(config.sections())
        if confsections:
            raise HelpfulError(
                "One or more required config sections are missing.",
                "Fix your config!"
                "Each [Section] should be on its own line with "
                "nothing else on it. The following sections are missing: {}".format(', '.join(['[%s]' % s for s in confsections])),
                preface="An error has occured parsing the config:\n"
            )
        self._confpreface = "An error has occured reading the config:\n"
        self._confpreface2 = "An error has occured validating the config:\n"

        self.auth = None

        self._login_token = config.get('Credentials', 'Token', fallback=ConfigDefaults.token)
        self.owner_id = config.get('Permissions', 'OwnerID', fallback=ConfigDefaults.owner_id)
        self.dev_ids = config.get('Permissions', 'DevIDs', fallback=ConfigDefaults.dev_ids)
        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback=ConfigDefaults.command_prefix)
        self.block_channels = config.get('Chat', 'BlockChannels', fallback=ConfigDefaults.block_channels)
        self.embeds = config.getboolean('Chat', 'Embeds', fallback=ConfigDefaults.embeds)

        self.debug_mode = config.getboolean('Bot', 'DebugMode', fallback=ConfigDefaults.debug_mode)
        self.debug_level = config.get('Bot', 'DebugLevel', fallback=ConfigDefaults.debug_level)
        self.debug_level_str = self.debug_level
        self.delete_messages = config.getboolean('Bot', 'DeleteMessages', fallback=ConfigDefaults.delete_messages)
        self.delete_invoking = config.getboolean('Bot', 'DeleteInvoking', fallback=ConfigDefaults.delete_invoking)
        self.timeout = config.getfloat('Bot', 'Timeout', fallback=ConfigDefaults.timeout)
        self.twitter_token = config.get('Bot', 'TwitterBearerToken', fallback=ConfigDefaults.twitter_token)
        self.enable_change_avatar = config.get('Bot', 'EnableChangeAvatar', fallback=ConfigDefaults.enable_change_avatar)
        self.blacklist_file = config.get('Files', 'BlacklistFile', fallback=ConfigDefaults.blacklist_file)
        self.banned_file = config.get('Files', 'BannedFile', fallback=ConfigDefaults.banned_file)
        self.webhook_file = config.get('Files', 'WebhookFile', fallback=ConfigDefaults.webhook_file)
        self.role_manager_file = config.get('Files', 'RoleManagerFile', fallback=ConfigDefaults.role_manager_file)
        self.reply_file = config.get('Files', 'ReplyFile', fallback=ConfigDefaults.reply_file)
<<<<<<< HEAD
=======
        self.magic_cat_file = config.get('Files', 'ImageFile', fallback=ConfigDefaults.magic_cat_file)
        self.font_file = config.get('Files', 'FontFile', fallback=ConfigDefaults.font_file)
>>>>>>> f0e191a... add reply magic cat image

        self.run_checks()

    def run_checks(self):
        """
        Validation logic for bot settings.
        """
        if not self._login_token:
            raise HelpfulError("No login credentials were specified in the config.", "Please fill in the Token field.", preface=self._confpreface)

        else:
            self.auth = self._login_token

        if self.owner_id:
            if self.owner_id.isdigit():
                if int(self.owner_id) < 10000:
                    raise HelpfulError(
                        "An invalid OwnerID was set: {}".format(self.owner_id), "Correct your OwnerID.  "
                        "The ID should be just a number, approximately "
                        "18 characters long.  "
                        "If you don't know what your ID is, read the "
                        "instructions in the config.ini file.",
                        preface=self._confpreface
                    )

            elif self.owner_id == 'auto':
                pass  # defer to async check

            else:
                self.owner_id = None

        if not self.owner_id:
            raise HelpfulError("No OwnerID was set.", "Please set the OwnerID option in {}".format(self.config_file), preface=self._confpreface)

        if self.dev_ids:
            try:
                self.dev_ids = set(x for x in self.dev_ids.split() if x)
            except Exception:
                LOG.warning("DevIDs data is invalid \
                    will not have any devs")
                self.dev_ids = set()

            self.dev_ids = set(int(item.replace(',', ' ').strip()) for item in self.dev_ids)

        if self.block_channels:
            try:
                self.block_channels = set(x for x in self.block_channels.split() if x)
            except Exception:
                LOG.warning("BlockChannels data is invalid, \
                    will not block any channels")
                self.block_channels = set()

            self.block_channels = set(int(item.replace(',', ' ').strip()) for item in self.block_channels)

        if hasattr(logging, self.debug_level.upper()):
            self.debug_level = getattr(logging, self.debug_level.upper())
        else:
            LOG.warning("Invalid DebugLevel option %s given, falling back to INFO", self.debug_level_str)
            self.debug_level = logging.INFO
            self.debug_level_str = 'INFO'

        self.debug_mode = self.debug_level <= logging.DEBUG

    async def async_validate(self, bot):
        """ TODO """
        LOG.debug("Validating config...")

        if self.owner_id == 'auto':
            if not bot.user.bot:
                raise HelpfulError(
                    "Invalid parameter \"auto\" for OwnerID option.", "Only bot accounts can use the \"auto\" option.  Please "
                    "set the OwnerID in the config.",
                    preface=self._confpreface2
                )

            self.owner_id = bot.cached_app_info.owner.id
            LOG.debug("Aquired owner id via API")

        self.owner_id = int(self.owner_id)

        if self.owner_id == bot.user.id:
            raise HelpfulError(
                "Your OwnerID is incorrect or you've used the "
                "wrong credentials.", "The bot's user ID and the id for OwnerID is identical.  "
                "This is wrong.  The bot needs its own account to function, "
                "meaning you cannot use your own account to run the bot on.  "
                "The OwnerID is the id of the owner, not the bot.  "
                "Figure out which one is which and use "
                "the correct information.",
                preface=self._confpreface2
            )
        self.dev_ids.add(self.owner_id)

    def find_config(self):
        """ TODO """
        config = configparser.ConfigParser(interpolation=None)

        if not os.path.isfile(self.config_file):
            if os.path.isfile(self.config_file + '.ini'):
                shutil.move(self.config_file + '.ini', self.config_file)
                LOG.info(
                    "Moving {0} to {1}, \
                         you should probably turn file extensions on.".format(self.config_file + '.ini', self.config_file)
                )

            elif os.path.isfile('config/example_config.ini'):
                shutil.copy('config/example_config.ini', self.config_file)
                LOG.warning('Config file not found, copying example_config.ini')

            else:
                raise HelpfulError(
                    "Your config files are missing. Neither config.ini nor "
                    "example_config.ini were found.", "Grab the files back from the archive or remake them "
                    "yourself and copy paste the content "
                    "from the repo. Stop removing important files!"
                )

        if not config.read(self.config_file, encoding='utf-8'):
            config = configparser.ConfigParser()
            try:
                # load the config again and check to see if the user edited
                # that one
                config.read(self.config_file, encoding='utf-8')

                # jake pls no flame
                if not int(config.get('Permissions', 'OwnerID', fallback=0)):
                    print(flush=True)
                    LOG.critical("""Please configure config/config.ini
                        and re-run the bot.""")
                    sys.exit(1)

            except ValueError:  # Config id value was changed but its not valid
                raise HelpfulError(
                    'Invalid value "{}" for OwnerID, config cannot be loaded.'.format(config.get('Permissions', 'OwnerID', fallback=None)),
                    """The OwnerID option takes a user id"""
                )

            except Exception as error:
                print(flush=True)
                LOG.critical("Unable to copy config/example_config.ini to %s", self.config_file, exc_info=error)
                sys.exit(2)


class ConfigDefaults:
    token = None
    owner_id = 'auto'
    timeout = 10.0
    dev_ids = set()
    command_prefix = '!'
    debug_mode = False
    debug_level = 'INFO'
    embeds = False
    block_channels = set()
    delete_invoking = False
    delete_messages = True
    twitter_token = None
    enable_change_avatar = False

    blacklist_file = 'config/blacklist.txt'
    banned_file = 'config/banned.txt'
    config_file = 'config/config.ini'
    bind_file = 'config/bind.txt'
    webhook_file = 'config/webhook.json'
    role_manager_file = 'config/role_manager.json'
<<<<<<< HEAD
    reply_file = 'config/reply_file.json'
=======
    reply_file = 'config/reply_file.json'
    magic_cat_file = 'resources/images/magic_cat.png'
    font_file = 'resources/fonts/WenQuanYi.ttf'
>>>>>>> f0e191a... add reply magic cat image
