import logging
import os
import sys
import tempfile
import traceback
import asyncio
import time

from kanobot import exceptions

TMPFILE = tempfile.TemporaryFile('w+', encoding='utf8')
LOG = logging.getLogger('launcher')
LOG.setLevel(logging.DEBUG)

sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(logging.Formatter(
    fmt="[%(levelname)s] %(name)s: %(message)s"
))
sh.setLevel(logging.INFO)
LOG.addHandler(sh)

tfh = logging.StreamHandler(stream=TMPFILE)
tfh.setFormatter(
    logging.Formatter(fmt="[%(relativeCreated).9f] %(asctime)s \
    - %(levelname)s - %(name)s: %(message)s"))
tfh.setLevel(logging.DEBUG)
LOG.addHandler(tfh)


def finalize_logging():
    """ TODO """
    if not os.path.isdir('logs'):
        os.mkdir('logs')

    if os.path.isfile("logs/bot.log"):
        LOG.info("Moving old bot log")
        try:
            if os.path.isfile("logs/bot.log.last"):
                os.unlink("logs/bot.log.last")
            os.rename("logs/bot.log", "logs/bot.log.last")
        except:
            pass

    with open("logs/bot.log", 'w', encoding='utf8') as file_:
        TMPFILE.seek(0)
        file_.write(TMPFILE.read())
        TMPFILE.close()

        file_.write('\n')
        file_.write(" PRE-RUN SANITY CHECKS PASSED ".center(80, '#'))
        file_.write('\n\n')

    global tfh
    LOG.removeHandler(tfh)
    del tfh

    fh = logging.FileHandler("logs/bot.log", mode='a')
    fh.setFormatter(logging.Formatter(
        fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
    ))
    fh.setLevel(logging.DEBUG)
    LOG.addHandler(fh)

    sh.setLevel(logging.INFO)

    dlog = logging.getLogger('discord')
    dlh = logging.StreamHandler(stream=sys.stdout)
    dlh.terminator = ''
    dlh.setFormatter(logging.Formatter('.'))
    dlog.addHandler(dlh)


def main():

    finalize_logging()
    max_wait_time = 60
    loops = 0

    while 1:
        bot = None
        try:
            from kanobot.bot import Kanobot
            bot = Kanobot()
            bot.run()

        except exceptions.HelpfulError as e:
            LOG.info(e.message)
            break
        except exceptions.TerminateSignal:
            break
        except exceptions.RestartSignal:
            loops = 0
            pass
        except Exception:
            LOG.exception("Error starting bot")

        finally:
            if not bot or not bot.init_ok:
                if any(sys.exc_info()):
                    # How to log this without redundant messages...
                    traceback.print_exc()
                break
            asyncio.set_event_loop(asyncio.new_event_loop())
            loops += 1

        sleeptime = min(loops * 2, max_wait_time)
        if sleeptime:
            LOG.info("Restarting in {} seconds...".format(sleeptime))
            time.sleep(sleeptime)
    print()
    LOG.info("All done.")


if __name__ == '__main__':
    main()
