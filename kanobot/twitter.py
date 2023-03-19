# from https://github.com/NNTin/discord-twitter-bot
import time
import json
import requests
import logging

from time import gmtime, strftime
from threading import Thread

from tweepy import StreamingClient

LOG = logging.getLogger(__name__)


def webhook_post(url, data):
    """
    Send the JSON formated object to the url.
    """
    result = requests.post(url, data=data)
    if 200 <= result.status_code <= 299 or result.text == "ok":
        return True
    else:
        try:
            jsonResult = json.loads(result.text)
            if jsonResult['message'] == 'You are being rate limited.':
                print(jsonResult)
                wait = int(jsonResult['retry_after'])
                wait = wait / 1000 + 0.1
                time.sleep(wait)
                webhook_post(url, data)
            else:
                LOG.warning('{}\n{}\n{}\n'.format(str(result.text), type(result.text), result.text))
        except Exception:
            LOG.warning('Unhandled Error! Look into this {}\n{}\n{}\n'.format(str(result.text), type(result.text), result.text))


class MyStreamingClient(StreamingClient):

    def __init__(self, bearer_token, dataD):
        super().__init__(bearer_token, wait_on_rate_limit=True)
        self.dataD = dataD

    def reset(self, dataD):
        self.dataD = dataD

    def on_data(self, rawdata):
        """Called when a new status arrives"""
        rawdata = json.loads(rawdata.decode('utf-8'))
        data = rawdata['data']

        # Skip not authored by
        if data['author_id'] not in self.dataD['twitter_ids']:
            return

        users = rawdata['includes']['users']
        user = users[0]
        name = user['name']
        profile_image_url = user['profile_image_url']
        username = user['username']
        userid = user['id']
        twitterid = data['id']

        LOG.info(strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + " " + name + "(" + username + ")" + ' twittered.')

        for dataDiscord in self.dataD.get('Discord', []):
            if userid != dataDiscord['twitter_id']:
                continue

            worthPosting = True
            # your followed Twitter users tweeting to random Twitter users
            # (relevant if you only want status updates/opt out of conversations)

            if 'referenced_tweets' in data:
                # This Tweet is a reply
                if data['referenced_tweets'][0]['type'] == 'replied_to':
                    if not dataDiscord['includeUserReply']:
                        worthPosting = False
                # This Tweet is a Retweet
                if data['referenced_tweets'][0]['type'] == 'retweeted':
                    username = users[1]['username']
                    name = users[1]['name']
                    profile_image_url = users[1]['profile_image_url']
                    twitterid = data['referenced_tweets'][0]['id']
                    if not dataDiscord['includeRetweet']:
                        worthPosting = False  # retweet
                # type == 'quoted' Tweet is a Retweet with reply

            if not worthPosting:
                continue

            wh_url = dataDiscord['webhook_url']
            url = "https://twitter.com/" + \
                username + \
                "/status/" + twitterid
            Thread(target=webhook_post, args=(wh_url, {'username': name, 'avatar_url': profile_image_url, 'content': url})).start()
        return True

    def on_connect(self):
        """Called once connected to streaming server.

        This will be invoked once a successful response
        is received from the server. Allows the listener
        to perform some work prior to entering the read loop.
        """
        LOG.info(strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + ' Twitter stream successful connected')
        return

    def on_error(self, status_code):
        """Called when a non-200 status code is returned"""
        LOG.warning(strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + f' Twitter stream on error({status_code}) retry in few second.')
        return

    def keep_alive(self):
        """Called when a keep-alive arrived"""
        LOG.debug(strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + ' Twitter stream keep-alive')
        return

    def on_exception(self, exception):
        """Called when an unhandled exception occurs."""
        LOG.debug(strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + exception)
        return
