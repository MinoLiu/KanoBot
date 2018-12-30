class Response:
    """ TODO """
    __slots__ = ['_content', 'reply', 'delete_after', 'codeblock', '_codeblock', 'embed']

    def __init__(self, content, reply=False, delete_after=0, codeblock=None, embed=True):
        self._content = content
        self.reply = reply
        self.delete_after = delete_after
        self.codeblock = codeblock
        self._codeblock = "```{!s}\n{{}}\n```".format('' if codeblock is True else codeblock)
        self.embed = embed

    @property
    def content(self):
        """ TODO """
        if self.codeblock:
            return self._codeblock.format(self._content)
        else:
            return self._content
