import shutil
import textwrap


# Base class for exceptions
class BotException(Exception):
    """ TODO """

    def __init__(self, message, *, expire_in=0):
        super().__init__(message)
        self._message = message
        self.expire_in = expire_in

    @property
    def message(self):
        """ TODO """
        return self._message

    @property
    def message_no_format(self):
        """ TODO """
        return self._message


# Something went wrong during the processing of a command
class CommandError(BotException):
    """ TODO """
    pass

# The user doesn't have permission to use a command


class PermissionsError(CommandError):
    """ TODO """
    @property
    def message(self):
        return "You don't have permission to use that command.\nReason: " + self._message


# Error with pretty formatting for hand-holding users through various errors
class HelpfulError(BotException):
    """ TODO """

    def __init__(self, issue, solution, *,
                 preface="An error has occured:", footnote='', expire_in=0):
        self.issue = issue
        self.solution = solution
        self.preface = preface
        self.footnote = footnote
        self.expire_in = expire_in
        self._message_fmt = """\n{preface}
                             \n{problem}
                             \n\n{solution}
                             \n\n{footnote}"""

    @property
    def message(self):
        return self._message_fmt.format(
            preface=self.preface,
            problem=self._pretty_wrap(self.issue, "  Problem:"),
            solution=self._pretty_wrap(self.solution, "  Solution:"),
            footnote=self.footnote
        )

    @property
    def message_no_format(self):
        return self._message_fmt.format(
            preface=self.preface,
            problem=self._pretty_wrap(self.issue, "  Problem:", width=None),
            solution=self._pretty_wrap(
                self.solution, "  Solution:", width=None),
            footnote=self.footnote
        )

    @staticmethod
    def _pretty_wrap(text, pretext, *, width=-1):
        if width is None:
            return '\n'.join((pretext.strip(), text))
        elif width == -1:
            pretext = pretext.rstrip() + '\n'
            width = shutil.get_terminal_size().columns

        lines = textwrap.wrap(text, width=width - 5)
        lines = (('    ' + line).
                 rstrip().ljust(width - 1).rstrip() + '\n' for line in lines)

        return pretext + ''.join(lines).rstrip()


class HelpfulWarning(HelpfulError):
    """ TODO """
    pass


# Base class for control signals
class Signal(Exception):
    """ TODO """
    pass


# signal to restart the bot
class RestartSignal(Signal):
    """ TODO """
    pass


# signal to end the bot "gracefully"
class TerminateSignal(Signal):
    """ TODO """
    pass
