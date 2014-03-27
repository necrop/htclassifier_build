"""
DBUpdater -- Update the thesaurus database with any new classifications
found in the first iteration (so that these are available in the
second iteration)
"""

import string

from pickler.sensemanager import PickleLoader
import lex.oed.thesaurus.thesaurusdb as tdb

letters = string.ascii_uppercase


class DbUpdater(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def update(self):
        for letter in letters:
            buffer = []
            pl = PickleLoader(self.input_dir, letters=letter)
            for sense in pl.iterate():
                if sense.definition is None:
                    # don't bother with undefined lemmas
                    pass
                else:
                    instances = tdb.search(refentry=sense.entry_id,
                                           refid=sense.node_id)
                    try:
                        instance = instances[0]
                    except IndexError:
                        pass
                    else:
                        buffer.append((instance, sense.class_id))
                        if len(buffer) > 1000:
                            tdb.add_links(buffer)
                            buffer = []
            tdb.add_links(buffer)
