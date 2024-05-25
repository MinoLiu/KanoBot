# KanoBot

[![CircleCI](https://circleci.com/gh/MinoLiu/KanoBot/tree/master.svg?style=shield)](https://circleci.com/gh/MinoLiu/KanoBot/tree/master) [![Docker Image Version (tag)](https://img.shields.io/docker/v/sean2525/kanobot/latest)](https://hub.docker.com/r/sean2525/kanobot/tags/) [![license:mit](https://img.shields.io/badge/license-mit-blue.svg)](https://opensource.org/licenses/MIT)

Kanobot is a Discord bot written in Python and uses the Rewrite version of [discord.py](https://discordpy.readthedocs.io/en/rewrite/)  
Adapted from [Just-Some-Bots/MusicBot](https://github.com/Just-Some-Bots/MusicBot) and [DiscordMusicBot/MusicBot](https://github.com/DiscordMusicBot/MusicBot)  
But remove the music features.

## TODO List

- [x] Purge message
- [x] Twitter subscribe support
- [x] Roles management
- [ ] Meme
- [ ] More cmd
- [ ] Bot status

## Installation

```bash
pip install pipenv
pipenv install --dev
```

## Configuration

- Copy config/example_config.ini to config/config.ini

```
cp config/example_config.ini config/config.ini
```

- bot_token must be replaced to correct token.

```ini
[Credentials]
; If you have a bot account (which you should), you can find your token here:
;     https://discordapp.com/developers/applications/me/
; Then click the button for your bot to go to the bot's page.
; Make sure "Require OAuth2 Code Grant" is unchecked.  You also do not need to
; add any "Redirect URIs" or "RPC Origins".
;
Token = bot_token
```

- Support twitter feature must be completed this

```ini
; Enable twitter webhook
; Go to https://developer.twitter.com/en/portal/projects-and-apps
; Setup project and link app
; Input BearerToken
TwitterBearerToken = 
```

## Run

- python

```
pipenv run python run.py
```

- Docker

```bash
docker run --rm -ti -d --name kanobot -v ${pwd}/config:/app/config -v ${pwd}/logs:/app/logs sean2525/kanobot
```

- docker-compose

```bash
docker-compose up -d
```

## Usage

```bash
# See available commands
!help

# Show bot invite link
!joinserver
...
```
