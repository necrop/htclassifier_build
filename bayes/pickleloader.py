import os
import string
import pickle


class PickleLoader(object):

    def __init__(self, directory, letters=None):
        if letters is not None:
            letters = letters.upper()
        self.dir = directory
        self.letters = letters

    def iterate(self, letters=None):
        if letters is not None:
            self.letters = letters.upper()

        for letter in string.ascii_uppercase:
            if self.letters is None or letter in self.letters:
                filepath = os.path.join(self.dir, letter)
                with open(filepath, 'rb') as filehandle:
                    while 1:
                        try:
                            yield pickle.load(filehandle)
                        except EOFError:
                            break
