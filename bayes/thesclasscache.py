import lex.oed.thesaurus.thesaurusdb as tdb


class ThesclassCache(object):
    cache = {}

    def __init__(self):
        pass

    def retrieve_thesclass(self, class_id):
        try:
            return ThesclassCache.cache[class_id]
        except KeyError:
            c = tdb.get_thesclass(class_id)
            ThesclassCache.cache[class_id] = c
            return c
