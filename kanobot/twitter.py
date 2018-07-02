from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy.api import API
import calendar
import datetime
import time
import random
import json
from time import gmtime, strftime
from datetime import datetime
import html
import requests
import logging
from .jsonIO import JsonIO

LOG = logging.getLogger(__name__)


class Webhook():
    def __init__(self, url):
        """
        Initialize a Discord Webhook object.
        @param {String} url - The webhook url where to make requests.
        """
        self.url = url

    def post(self, data):
        """
        Send the JSON formated object to the specified `self.url`.
        """
        result = requests.post(self.url, data=data)

        if 200 <= result.status_code <= 299 or result.text == "ok":
            return True
        else:
            try:
                jsonResult = json.loads(result.text)
                if jsonResult['message'] == 'You are being rate limited.':
                    print(jsonResult)
                    wait = int(jsonResult['retry_after'])
                    wait = wait/1000 + 0.1
                    time.sleep(wait)
                    self.post(data)
                else:
                    LOG.warning('{}\n{}\n{}\n'.format(
                        str(result.text), type(result.text), result.text))
            except:
                # raise Exception("Error on post : " + str(result))
                LOG.warning('Unhandled Error! Look into this {}\n{}\n{}\n'.format(
                    str(result.text), type(result.text), result.text))


class StdOutListener(StreamListener):
    def __init__(self, dataD, api=None):
        self.api = api or API()
        self.dataD = dataD

    def reset(self, dataD):
        self.dataD = dataD

    def on_status(self, status):
        """Called when a new status arrives"""

        data = status._json

        if data['user']['id_str'] not in self.dataD['twitter_ids']:
            return True

        LOG.info(strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + " " +
                 data['user']['screen_name']+' twittered.')

        for dataDiscord in self.dataD.get('Discord', []):
            if data['user']['id_str'] != dataDiscord['twitter_id']:
                worthPosting = False
                if 'IncludeReplyToUser' in dataDiscord:  # other Twitter user tweeting to your followed Twitter user
                    if dataDiscord['IncludeReplyToUser'] == True:
                        if data['in_reply_to_user_id_str'] == dataDiscord['twitter_id']:
                            worthPosting = True
            else:
                worthPosting = True
                # your followed Twitter users tweeting to random Twitter users (relevant if you only want status updates/opt out of conversations)
                if 'IncludeUserReply' in dataDiscord:
                    if dataDiscord['IncludeUserReply'] == False and data['in_reply_to_user_id'] is not None:
                        worthPosting = False

            if 'IncludeRetweet' in dataDiscord:  # retweets...
                if dataDiscord['IncludeRetweet'] == False:
                    if 'retweeted_status' in data:
                        worthPosting = False  # retweet

            if not worthPosting:
                continue

            wh_url = dataDiscord['webhook_url']
            username = data['user']['name']
            avatar_url = data['user']['profile_image_url']

            url = "https://twitter.com/" + \
                data['user']['screen_name'] + \
                "/status/" + str(data['id_str'])

            wh = Webhook(url=wh_url)
            wh.post({'username': username, 'avatar_url': avatar_url, 'content': url})
        return True

    def on_connect(self):
        """Called once connected to streaming server.

        This will be invoked once a successful response
        is received from the server. Allows the listener
        to perform some work prior to entering the read loop.
        """
        LOG.info('Twitter stream success connected')
        return

    def on_error(self, status_code):
        """Called when a non-200 status code is returned"""
        LOG.warning(
            'Twitter stream on error({}) retry in few second.'.format(status_code))
        return
